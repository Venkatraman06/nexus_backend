from rest_framework.viewsets import ModelViewSet
from apps.common.permissions import IsAuthenticated
from .models import Lead, LeadActivity, LeadTask, LeadDocument, Client
from .serializers import (
    LeadSerializer, LeadActivitySerializer,
    LeadTaskSerializer, LeadDocumentSerializer, ClientSerializer,
)


class LeadViewSet(ModelViewSet):
    queryset = Lead.objects.filter(is_deleted=False).order_by("-created_at")
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        try:
            old_instance = self.get_object()
            old_status = old_instance.status
        except Exception:
            old_status = None

        instance = serializer.save(updated_by=self.request.user)

        if instance.status == "WON":
            # Try to resolve assigned_to UUID to a name
            if instance.assigned_to and not instance.assigned_to_name:
                try:
                    from apps.accounts.models import Employee
                    emp = Employee.objects.filter(id=instance.assigned_to).first()
                    if emp:
                        instance.assigned_to_name = emp.full_name
                        instance.save(update_fields=['assigned_to_name'])
                except Exception:
                    pass

            from django.utils import timezone
            auto_note = f"Auto-converted from Lead #{instance.id} on {timezone.now().strftime('%Y-%m-%d')}"
            
            client = Client.objects.filter(name=instance.name, is_deleted=False).first()
            if not client:
                client = Client.objects.create(
                    name=instance.name,
                    company=instance.company,
                    college=instance.college,
                    contact_person=instance.contact_person,
                    phone=instance.phone,
                    whatsapp=instance.whatsapp,
                    email=instance.email,
                    notes=auto_note,
                    deal_title=instance.deal_title or "",
                    deal_description=instance.deal_description or "",
                    deal_amount=instance.deal_amount or instance.expected_deal_value,
                    deal_date_from=instance.deal_date_from,
                    deal_date_to=instance.deal_date_to,
                    created_by=self.request.user,
                    updated_by=self.request.user,
                )
            else:
                if "Auto-converted" not in (client.notes or ""):
                    client.notes = (client.notes + "\n" + auto_note).strip() if client.notes else auto_note
                    client.save(update_fields=["notes"])

            # Auto-create/sync Sales Opportunity Deal
            try:
                from apps.sales.models import Deal
                deal_title = instance.deal_title or f"Opportunity for {instance.name}"
                deal_amount = instance.deal_amount or instance.expected_deal_value or 0
                deal_desc = instance.deal_description or f"Converted from Lead #{instance.id}"
                
                deal = Deal.objects.filter(client=client, is_deleted=False).first()
                if not deal:
                    Deal.objects.create(
                        client=client,
                        title=deal_title,
                        description=deal_desc,
                        expected_value=deal_amount,
                        stage="Won",
                        created_by=self.request.user,
                        updated_by=self.request.user,
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to auto-create Deal: %s", e)

        elif old_status == "WON" and instance.status != "WON":
            # Undo conversion — delete matching auto-created Client & Deal records
            clients = Client.objects.filter(is_deleted=False)
            match = None
            if instance.email:
                match = clients.filter(email__iexact=instance.email).first()
            if not match:
                match = clients.filter(name__iexact=instance.name, contact_person__iexact=instance.contact_person).first()
            if match:
                try:
                    from apps.sales.models import Deal
                    Deal.objects.filter(client=match, is_deleted=False).update(is_deleted=True)
                except Exception:
                    pass
                match.soft_delete(user=self.request.user)

class LeadActivityViewSet(ModelViewSet):
    queryset = LeadActivity.objects.filter(is_deleted=False).order_by("-created_at")
    serializer_class = LeadActivitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get("lead")
        if lead_id:
            qs = qs.filter(lead_id=lead_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class LeadTaskViewSet(ModelViewSet):
    queryset = LeadTask.objects.filter(is_deleted=False).order_by("-created_at")
    serializer_class = LeadTaskSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class LeadDocumentViewSet(ModelViewSet):
    queryset = LeadDocument.objects.filter(is_deleted=False).order_by("-uploaded_at")
    serializer_class = LeadDocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class ClientViewSet(ModelViewSet):
    queryset = Client.objects.filter(is_deleted=False).order_by("-created_at")
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)