from rest_framework.viewsets import ModelViewSet
from apps.common.permissions import IsAuthenticated

from .serializers import (
    LeadSerializer, LeadActivitySerializer,
    LeadTaskSerializer, LeadDocumentSerializer, ClientSerializer,
    ClientChatRoomSerializer, ClientChatMessageSerializer,
)
from .models import Lead, LeadActivity, LeadTask, LeadDocument, Client, ClientChatRoom, ClientChatMessage


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
            if instance.assigned_to and not instance.assigned_to_name:
                try:
                    from apps.accounts.models import Employee
                    emp = Employee.objects.filter(id=instance.assigned_to).first()
                    if emp:
                        instance.assigned_to_name = emp.full_name
                        instance.save(update_fields=['assigned_to_name'])
                except Exception:
                    pass

            client, _ = Client.objects.get_or_create(
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

            assigned_ids = self.request.data.get("assigned_employee_ids")
            if assigned_ids:
                from apps.accounts.models import Employee
                employees = Employee.objects.filter(id__in=assigned_ids)
                client.assigned_employees.set(employees)

                room, _ = ClientChatRoom.objects.get_or_create(
                    client=client,
                    defaults={"name": f"{client.name} — Project Chat", "created_by": self.request.user, "updated_by": self.request.user},
                )
                participants = list(employees)
                if self.request.user not in participants:
                    participants.append(self.request.user)
                room.participants.set(participants)


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


class ClientChatRoomViewSet(ModelViewSet):
    serializer_class = ClientChatRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ClientChatRoom.objects.filter(is_deleted=False).order_by("-created_at")
        if getattr(user, "is_superuser", False) or getattr(user, "is_pmo", False):
            return qs
        return qs.filter(participants=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class ClientChatMessageViewSet(ModelViewSet):
    serializer_class = ClientChatMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ClientChatMessage.objects.filter(is_deleted=False).order_by("created_at")
        room_id = self.request.query_params.get("room")
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user, created_by=self.request.user, updated_by=self.request.user)