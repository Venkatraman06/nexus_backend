

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
        try:
            old_instance = self.get_object()
            old_status = old_instance.status
        except Exception:
            old_status = None

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

            client, created = Client.objects.get_or_create(
                name=instance.name,
                defaults={
                    "company": instance.company or "",
                    "college": instance.college or "",
                    "contact_person": instance.contact_person or "",
                    "phone": instance.phone or "",
                    "whatsapp": instance.whatsapp or "",
                    "email": instance.email or "",
                    "notes": instance.notes or "",
                    "relationship_score": 80,
                    "business_category": instance.business_category or "",
                    "deal_title": instance.deal_title or "",
                    "deal_description": instance.deal_description or "",
                    "deal_amount": instance.deal_amount or None,
                    "deal_date_from": instance.deal_date_from or None,
                    "deal_date_to": instance.deal_date_to or None,
                    "created_by": self.request.user,
                    "updated_by": self.request.user,
                }
            )

            # Always sync deal fields onto the client (handles re-conversion too)
            if not created:
                update_fields = []
                for field, val in [
                    ("company", instance.company or ""),
                    ("college", instance.college or ""),
                    ("contact_person", instance.contact_person or ""),
                    ("phone", instance.phone or ""),
                    ("whatsapp", instance.whatsapp or ""),
                    ("email", instance.email or ""),
                    ("business_category", instance.business_category or ""),
                    ("deal_title", instance.deal_title or ""),
                    ("deal_description", instance.deal_description or ""),
                    ("deal_amount", instance.deal_amount or None),
                    ("deal_date_from", instance.deal_date_from or None),
                    ("deal_date_to", instance.deal_date_to or None),
                ]:
                    setattr(client, field, val)
                    update_fields.append(field)
                client.updated_by = self.request.user
                update_fields.append("updated_by")
                client.save(update_fields=update_fields)

            # Sync assigned employees from request
            assigned_ids = self.request.data.get("assigned_employee_ids") or []
            if assigned_ids:
                from apps.accounts.models import Employee
                employees = list(Employee.objects.filter(id__in=assigned_ids))
                client.assigned_employees.set(employees)
                print("DEBUG: client id =", client.id)
                print("DEBUG: employees set =", [str(e.id) for e in employees])
                print("DEBUG: client.assigned_employees.all() =", list(client.assigned_employees.all()))
                print("DEBUG: assigned_ids from request =", assigned_ids)

                room, _ = ClientChatRoom.objects.get_or_create(
                    client=client,
                    defaults={
                        "name": f"{client.name} — Project Chat",
                        "created_by": self.request.user,
                        "updated_by": self.request.user,
                    },
                )
                participants = list(employees)
                if self.request.user not in participants:
                    participants.append(self.request.user)
                room.participants.set(participants)
            else:
                # Clear employees if none sent
                client.assigned_employees.clear()

            # Auto-sync Sales Deal
            from apps.sales.models import Deal
            from decimal import Decimal
            deal_val = instance.deal_amount if instance.deal_amount is not None else Decimal("0.00")
            deal_title = instance.deal_title or instance.name or "Converted Opportunity"
            deal, deal_created = Deal.objects.get_or_create(
                client=client,
                defaults={
                    "title": deal_title,
                    "description": instance.deal_description or instance.notes or "",
                    "expected_value": deal_val,
                    "stage": "Active",
                    "created_by": self.request.user,
                    "updated_by": self.request.user,
                }
            )
            if not deal_created:
                if deal_val and deal_val > 0:
                    deal.expected_value = deal_val
                if instance.deal_title:
                    deal.title = instance.deal_title
                deal.save()


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