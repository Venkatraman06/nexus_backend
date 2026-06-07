from decimal import Decimal
from datetime import date

from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from drf_spectacular.utils import extend_schema

from .models import Payroll, PayrollStatus
from .serializers import PayrollSerializer
from .pdf import generate_payslip_pdf
from .services import generate_payroll


class PayrollListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.view"

    @extend_schema(tags=["payroll"])
    def get(self, request):
        qs = Payroll.objects.filter(is_deleted=False).select_related(
            "employee", "employee__designation_ref", "employee__department_ref"
        )
        # Filters
        emp_id = request.query_params.get("employee")
        month  = request.query_params.get("month")
        year   = request.query_params.get("year")
        st     = request.query_params.get("status")
        if emp_id: qs = qs.filter(employee_id=emp_id)
        if month:  qs = qs.filter(month=month)
        if year:   qs = qs.filter(year=year)
        if st:     qs = qs.filter(status=st)

        # Summary
        all_qs = Payroll.objects.filter(is_deleted=False)
        summary = {
            "total":     all_qs.count(),
            "draft":     all_qs.filter(status=PayrollStatus.DRAFT).count(),
            "finalized": all_qs.filter(status=PayrollStatus.FINALIZED).count(),
            "paid":      all_qs.filter(status=PayrollStatus.PAID).count(),
            "total_net": float(all_qs.filter(status__in=[PayrollStatus.FINALIZED, PayrollStatus.PAID])
                               .aggregate(t=Sum("basic_salary"))["t"] or 0),
        }

        return Response({
            "summary": summary,
            "results": PayrollSerializer(qs, many=True).data,
        })

    @extend_schema(tags=["payroll"])
    def post(self, request):
        # Check create permission separately
        if not (request.user.is_staff or getattr(request.user, "is_superuser", False)):
            perms = getattr(request, "user_permissions", [])
            if "pmt.hrms.payroll.create" not in perms:
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = PayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Auto-compute PF if not provided
        data = serializer.validated_data
        if not data.get("pf") and data.get("basic_salary", 0) > 0:
            data["pf"] = round(data["basic_salary"] * Decimal("0.12"), 2)

        payroll = serializer.save(created_by=request.user)
        return Response(PayrollSerializer(payroll).data, status=status.HTTP_201_CREATED)


class PayrollDetailView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.view"

    def _get(self, pk):
        try:
            return Payroll.objects.select_related(
                "employee", "employee__designation_ref", "employee__department_ref"
            ).get(pk=pk, is_deleted=False)
        except Payroll.DoesNotExist:
            return None

    @extend_schema(tags=["payroll"])
    def get(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PayrollSerializer(obj).data)

    @extend_schema(tags=["payroll"])
    def patch(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = PayrollSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(PayrollSerializer(obj).data)

    @extend_schema(tags=["payroll"])
    def delete(self, request, pk):
        obj = self._get(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        obj.is_deleted = True
        obj.save(update_fields=["is_deleted"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayrollApproveView(APIView):
    """Finalize (approve) a payroll — moves DRAFT → FINALIZED."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.approve"

    @extend_schema(tags=["payroll"])
    def post(self, request, pk):
        try:
            obj = Payroll.objects.get(pk=pk, is_deleted=False)
        except Payroll.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if obj.status != PayrollStatus.DRAFT:
            return Response({"detail": "Only DRAFT payrolls can be finalized."},
                            status=status.HTTP_400_BAD_REQUEST)
        obj.status = PayrollStatus.FINALIZED
        obj.save(update_fields=["status"])

        from apps.notifications.constants import EventType, ReferenceType
        from apps.notifications.publisher import publish_event
        publish_event(
            EventType.PAYROLL_FINALIZED,
            ReferenceType.PAYROLL,
            str(obj.id),
            payload={
                "employee_id": str(obj.employee_id),
                "period": f"{obj.month_name} {obj.year}",
                "net_pay": str(obj.net_salary),
            },
            actor_id=str(request.user.id),
            async_delivery=True,
        )

        return Response(PayrollSerializer(obj).data)


class PayrollMarkPaidView(APIView):
    """Mark a FINALIZED payroll as PAID."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.approve"

    @extend_schema(tags=["payroll"])
    def post(self, request, pk):
        try:
            obj = Payroll.objects.get(pk=pk, is_deleted=False)
        except Payroll.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if obj.status != PayrollStatus.FINALIZED:
            return Response({"detail": "Only FINALIZED payrolls can be marked as PAID."},
                            status=status.HTTP_400_BAD_REQUEST)
        obj.status = PayrollStatus.PAID
        obj.save(update_fields=["status"])
        return Response(PayrollSerializer(obj).data)


class PayslipPDFView(APIView):
    """Generate and return payslip PDF (admin/PMO)."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.view"

    def get(self, request, pk):
        try:
            obj = Payroll.objects.select_related(
                "employee",
                "employee__designation_ref",
                "employee__department_ref",
            ).get(pk=pk, is_deleted=False)
        except Payroll.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        pdf_bytes = generate_payslip_pdf(obj)
        emp_name  = obj.employee.full_name.replace(" ", "-")
        filename  = f"Payslip-{emp_name}-{obj.month_name}-{obj.year}.pdf"

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class MyPayslipsView(APIView):
    """
    Employee self-service: list own payslips.
    GET /payroll/my/?year=2026
    Requires only authentication — no admin permission needed.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = request.query_params.get("year")
        qs = Payroll.objects.filter(
            employee=request.user, is_deleted=False
        ).select_related("employee", "employee__designation_ref", "employee__department_ref").order_by("-year", "-month")
        if year:
            qs = qs.filter(year=year)
        return Response({"results": PayrollSerializer(qs, many=True).data})


class PayrollGenerateView(APIView):
    """
    GET  /payroll/generate/?employee_id=&month=&year=
         → Preview calculated values from rate card + attendance (no DB write).

    POST /payroll/generate/
    Body: { employee_id, month, year }
         → Creates / updates a DRAFT payroll entry.
    """
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.create"

    @extend_schema(tags=["payroll"])
    def get(self, request):
        """Preview payroll calculation without saving."""
        from apps.accounts.models import Employee
        from apps.payroll.services import (
            _working_days_in_month, _tds,
        )
        from apps.master.models import RateCard
        from apps.attendance.models import AttendanceRecord, AttendanceStatus
        from decimal import Decimal, ROUND_HALF_UP
        import calendar

        emp_id = request.query_params.get("employee_id")
        month  = request.query_params.get("month")
        year   = request.query_params.get("year")

        if not all([emp_id, month, year]):
            return Response({"detail": "employee_id, month and year are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            employee = Employee.objects.select_related(
                "designation_ref", "department_ref"
            ).get(pk=emp_id, is_active=True, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        rate_card = RateCard.objects.filter(
            designation_ref_id=employee.designation_ref_id,
            department_ref_id=employee.department_ref_id,
            is_active=True,
        ).first()

        month_int = int(month)
        year_int  = int(year)
        total_working = _working_days_in_month(year_int, month_int)

        att_qs = AttendanceRecord.objects.filter(
            employee=employee,
            date__year=year_int,
            date__month=month_int,
            is_deleted=False,
        )
        present_days = att_qs.filter(
            status__in=[AttendanceStatus.PRESENT, AttendanceStatus.WFH]
        ).count()
        half_days  = att_qs.filter(status=AttendanceStatus.HALF_DAY).count()
        leave_days = att_qs.filter(status=AttendanceStatus.ON_LEAVE).count()

        if not rate_card:
            return Response({
                "has_rate_card": False,
                "working_days":  total_working,
                "present_days":  present_days,
                "leave_days":    leave_days,
                "message": (
                    f"No rate card for "
                    f"{getattr(employee.designation_ref, 'name', '?')} / "
                    f"{getattr(employee.department_ref, 'name', '?')}. "
                    f"Enter salary manually."
                ),
            })

        payable_days = Decimal(present_days) + Decimal(half_days) * Decimal("0.5")
        monthly_ctc  = (rate_card.hr_daily_rate * payable_days).quantize(Decimal("0.01"), ROUND_HALF_UP)
        basic        = (monthly_ctc * Decimal("0.40")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        hra          = (monthly_ctc * Decimal("0.20")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        allowances   = (monthly_ctc - basic - hra).quantize(Decimal("0.01"), ROUND_HALF_UP)
        pf           = (basic * Decimal("0.12")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        tds          = _tds(monthly_ctc * 12).quantize(Decimal("0.01"), ROUND_HALF_UP)

        return Response({
            "has_rate_card":       True,
            "designation":         getattr(employee.designation_ref, "name", ""),
            "department":          getattr(employee.department_ref, "name", ""),
            "hr_daily_rate":       float(rate_card.hr_daily_rate),
            "client_billing_rate": float(rate_card.client_billing_rate),
            "payable_days":        float(payable_days),
            "working_days":        total_working,
            "present_days":        present_days,
            "leave_days":          leave_days,
            "basic_salary":        float(basic),
            "hra":                 float(hra),
            "allowances":          float(allowances),
            "overtime":            0,
            "pf":                  float(pf),
            "tds":                 float(tds),
            "other_deductions":    0,
            "advance_deduction":   0,
        })

    @extend_schema(tags=["payroll"])
    def post(self, request):
        from apps.accounts.models import Employee
        emp_id = request.data.get("employee_id")
        month  = request.data.get("month")
        year   = request.data.get("year")

        if not all([emp_id, month, year]):
            return Response({"detail": "employee_id, month and year are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            employee = Employee.objects.get(pk=emp_id, is_active=True, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        payroll, created, error = generate_payroll(
            employee=employee,
            month=int(month),
            year=int(year),
            created_by=request.user,
        )
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"created": created, **PayrollSerializer(payroll).data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PayrollBulkGenerateView(APIView):
    """
    POST /payroll/generate/bulk/
    Body: { month, year }

    Generates payroll for ALL active shift employees who have a matching rate card.
    """
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.payroll.create"

    @extend_schema(tags=["payroll"])
    def post(self, request):
        from apps.accounts.models import Employee
        month = request.data.get("month")
        year  = request.data.get("year")
        if not all([month, year]):
            return Response({"detail": "month and year are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        employees = Employee.objects.filter(
            is_active=True, is_deleted=False,
            shift_applicable=True,
        ).select_related("designation_ref", "department_ref")

        results = {"generated": 0, "updated": 0, "skipped": 0, "errors": []}
        for emp in employees:
            payroll, created, error = generate_payroll(
                employee=emp,
                month=int(month),
                year=int(year),
                created_by=request.user,
            )
            if error:
                results["errors"].append({"employee": emp.full_name, "error": error})
                results["skipped"] += 1
            elif created:
                results["generated"] += 1
            else:
                results["updated"] += 1

        return Response(results, status=status.HTTP_200_OK)


class MyPayslipPDFView(APIView):
    """
    Employee self-service: download own payslip PDF.
    GET /payroll/my/<pk>/payslip-pdf/
    Only allowed if the payroll belongs to the requesting employee.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            obj = Payroll.objects.select_related(
                "employee",
                "employee__designation_ref",
                "employee__department_ref",
            ).get(pk=pk, is_deleted=False, employee=request.user)
        except Payroll.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        pdf_bytes = generate_payslip_pdf(obj)
        emp_name  = obj.employee.full_name.replace(" ", "-")
        filename  = f"Payslip-{emp_name}-{obj.month_name}-{obj.year}.pdf"

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
