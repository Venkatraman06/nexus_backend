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

            Client.objects.get_or_create(
                name=instance.name,
                defaults={
                    "company": instance.company,
                    "college": instance.college,
                    "contact_person": instance.contact_person,
                    "phone": instance.phone,
                    "whatsapp": instance.whatsapp,
                    "email": instance.email,
                    "notes": instance.notes,
                }
            )

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