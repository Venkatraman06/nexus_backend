from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .views import MeView
from .selfservice_models import EmployeeEmergencyContact, EmployeeDocument
from .selfservice_serializers import EmployeeEmergencyContactSerializer, EmployeeDocumentSerializer


class SelfServiceMeView(MeView):
    """
    Subclass of MeView to add extra editable fields like Address, DOB, Gender,
    Alternative number, and Emergency Contacts without changing the original view.
    """
    def get(self, request):
        response = super().get(request)
        me = request.user

        # Load emergency contact
        emergency_contact_data = None
        try:
            if hasattr(me, "emergency_contact") and me.emergency_contact:
                serializer = EmployeeEmergencyContactSerializer(me.emergency_contact)
                emergency_contact_data = serializer.data
        except Exception:
            pass

        # Update response data with the extra fields
        response.data.update({
            "alternative_number": getattr(me, "alternative_number", "") or "",
            "address": getattr(me, "address", "") or "",
            "date_of_birth": str(me.date_of_birth) if getattr(me, "date_of_birth", None) else None,
            "gender": getattr(me, "gender", "") or "",
            "emergency_contact": emergency_contact_data,
        })
        return response

    @extend_schema(tags=["users"])
    def patch(self, request):
        from apps.common.validators import validate_phone
        from rest_framework.exceptions import ValidationError

        me = request.user
        allowed = {
            "first_name", "last_name", "phone_number", "alternative_number",
            "bio", "profile_picture", "address", "date_of_birth", "gender"
        }
        update_fields = []

        # Parse basic fields
        for field in allowed:
            if field in request.data:
                value = request.data[field]
                if field == "phone_number" and value:
                    try:
                        value = validate_phone(value, "Phone number")
                    except ValidationError as exc:
                        return Response(exc.detail, status=400)
                elif field == "alternative_number" and value:
                    try:
                        value = validate_phone(value, "Alternative phone number")
                    except ValidationError as exc:
                        return Response(exc.detail, status=400)
                elif field == "date_of_birth" and (value == "" or value is None):
                    value = None

                setattr(me, field, value)
                update_fields.append(field)

        # Parse profile picture
        if "profile_picture" in request.FILES:
            me.profile_picture = request.FILES["profile_picture"]
            if "profile_picture" not in update_fields:
                update_fields.append("profile_picture")

        if update_fields:
            me.save(update_fields=update_fields)

        # Parse emergency contact nested JSON
        import json
        emergency_contact_data = request.data.get("emergency_contact")
        if emergency_contact_data:
            # Handle multipart form data stringified JSON
            if isinstance(emergency_contact_data, str):
                try:
                    emergency_contact_data = json.loads(emergency_contact_data)
                except Exception:
                    pass

            if emergency_contact_data is None:
                try:
                    if hasattr(me, "emergency_contact") and me.emergency_contact:
                        me.emergency_contact.delete()
                except Exception:
                    pass
            else:
                contact, created = EmployeeEmergencyContact.objects.get_or_create(employee=me)
                serializer = EmployeeEmergencyContactSerializer(contact, data=emergency_contact_data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()

        # Build response
        profile_pic_url = None
        try:
            profile_pic_url = me.profile_picture.url if me.profile_picture else None
        except Exception:
            pass

        updated_contact_data = None
        try:
            if hasattr(me, "emergency_contact") and me.emergency_contact:
                serializer = EmployeeEmergencyContactSerializer(me.emergency_contact)
                updated_contact_data = serializer.data
        except Exception:
            pass

        return Response({
            "detail": "Profile updated successfully.",
            "full_name": me.full_name,
            "profile_picture_url": profile_pic_url,
            "alternative_number": getattr(me, "alternative_number", "") or "",
            "address": getattr(me, "address", "") or "",
            "date_of_birth": str(me.date_of_birth) if getattr(me, "date_of_birth", None) else None,
            "gender": getattr(me, "gender", "") or "",
            "emergency_contact": updated_contact_data,
        })


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet to manage employee's personal uploaded documents (ID card, PAN, Passport, Certificates).
    Scoped to the current logged-in employee unless they are an admin/staff.
    """
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff or getattr(user, "is_pmo", False):
            return EmployeeDocument.objects.all().select_related("employee")
        return EmployeeDocument.objects.filter(employee=user).select_related("employee")

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user)
