from django.utils import timezone
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.common.permissions import IsAuthenticated
from .models import TrainingCategory, Deal, Quotation
from .serializers import TrainingCategorySerializer, DealSerializer, QuotationSerializer

signer = TimestampSigner()


class TrainingCategoryViewSet(viewsets.ModelViewSet):
    queryset = TrainingCategory.objects.filter(is_deleted=False).order_by("name")
    serializer_class = TrainingCategorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.filter(is_deleted=False).order_by("-created_at")
    serializer_class = DealSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        stage = self.request.query_params.get("stage")
        client_id = self.request.query_params.get("client")
        if stage:
            qs = qs.filter(stage=stage)
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.filter(is_deleted=False).order_by("-created_at")
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        quote_status = self.request.query_params.get("status")
        client_id = self.request.query_params.get("client")
        if quote_status:
            qs = qs.filter(status=quote_status)
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="send_mail")
    def send_mail(self, request, pk=None):
        quotation = self.get_object()

        recipient_email = request.data.get("email")
        if not recipient_email and quotation.client and quotation.client.email:
            recipient_email = quotation.client.email

        if not recipient_email:
            return Response(
                {"detail": "No email address provided for client. Please enter an email address to send the quotation."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save recipient email to client if missing
        if quotation.client and not quotation.client.email:
            quotation.client.email = recipient_email
            quotation.client.save(update_fields=["email"])

        quotation.status = "SENT"
        quotation.sent_at = timezone.now()
        quotation.save(update_fields=["status", "sent_at", "updated_at"])

        try:
            from django.core.mail import send_mail
            from django.conf import settings
            token = signer.sign(str(quotation.id))
            origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', ['http://localhost:3000'])
            base_url = origins[0] if isinstance(origins, (list, tuple)) and origins else 'http://localhost:3000'
            view_url = f"{base_url}/api/v1/quotations/{quotation.id}/view/?token={token}"
            approve_url = f"{base_url}/api/v1/quotations/{quotation.id}/respond/?token={token}&decision=approve"
            reject_url = f"{base_url}/api/v1/quotations/{quotation.id}/respond/?token={token}&decision=reject"
            
            client_name = quotation.client.name if quotation.client else "Valued Client"
            body = (
                f"Dear {client_name},\n\n"
                f"Please find your price quotation {quotation.quote_no} for net amount ₹{quotation.net_amount}.\n\n"
                f"Quotation Details:\n"
                f"- Quote No: {quotation.quote_no}\n"
                f"- Net Amount: ₹{quotation.net_amount}\n\n"
                f"View Quotation: {view_url}\n"
                f"Approve Quotation: {approve_url}\n"
                f"Reject Quotation: {reject_url}\n\n"
                f"Thank you!"
            )
            send_mail(
                subject=f"Price Quotation {quotation.quote_no} - {client_name}",
                message=body,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[recipient_email],
                fail_silently=True,
            )
        except Exception:
            pass

        serializer = self.get_serializer(quotation)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_view_quotation(request, pk=None):
    token = request.query_params.get("token")
    try:
        quotation = Quotation.objects.get(pk=pk, is_deleted=False)
    except Quotation.DoesNotExist:
        return Response({"detail": "Quotation not found"}, status=status.HTTP_404_NOT_FOUND)

    # Mark as viewed if token is provided or if accessed
    if not quotation.viewed_at:
        quotation.viewed_at = timezone.now()
        quotation.save(update_fields=["viewed_at", "updated_at"])

    serializer = QuotationSerializer(quotation)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def public_respond_quotation(request, pk=None):
    decision = request.query_params.get("decision") or request.data.get("decision")
    if not decision or decision.lower() not in ["approve", "reject"]:
        return Response({"detail": "Invalid decision. Use 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        quotation = Quotation.objects.get(pk=pk, is_deleted=False)
    except Quotation.DoesNotExist:
        return Response({"detail": "Quotation not found"}, status=status.HTTP_404_NOT_FOUND)

    new_status = "APPROVED" if decision.lower() == "approve" else "REJECTED"
    quotation.status = new_status
    quotation.responded_at = timezone.now()
    quotation.save(update_fields=["status", "responded_at", "updated_at"])

    serializer = QuotationSerializer(quotation)
    return Response(serializer.data, status=status.HTTP_200_OK)
