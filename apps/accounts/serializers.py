from rest_framework import serializers

from apps.common.validators import validate_phone
from .models import Employee


EMPLOYEE_COMMON_FIELDS = [
    "alternative_number", "address",
    "shift_category", "custom_shift_start", "custom_shift_end",
]

NEW_SHIFT_FIELDS = ["shift_category", "custom_shift_start", "custom_shift_end"]


class EmployeeListSerializer(serializers.ModelSerializer):
    full_name            = serializers.CharField(read_only=True)
    designation_name     = serializers.CharField(source="designation_ref.name", read_only=True, default=None)
    department_name      = serializers.CharField(source="department_ref.name",  read_only=True, default=None)
    location_name        = serializers.CharField(source="location.name",        read_only=True, default=None)
    grade_name           = serializers.CharField(source="grade.name",           read_only=True, default=None)
    employment_type_name = serializers.CharField(source="employment_type.name", read_only=True, default=None)
    shift_category_name  = serializers.CharField(source="shift_category.name",  read_only=True, default=None)
    manager_name         = serializers.CharField(source="manager.full_name",    read_only=True, default=None)

    class Meta:
        model = Employee
        fields = [
            "id", "keycloak_id", "username", "email",
            "first_name", "last_name", "full_name",
            "employee_code", "designation", "department",
            "designation_ref", "designation_name",
            "department_ref", "department_name",
            "location", "location_name",
            "grade", "grade_name",
            "employment_type", "employment_type_name",
            "gender", "date_of_birth", "joining_date", "phone_number",
            "alternative_number", "address",
            "manager", "manager_name",
            "status", "is_active", "is_pmo", "is_manager", "is_staff",
            "shift_applicable", "shift_category", "shift_category_name",
            "custom_shift_start", "custom_shift_end",
            "keycloak_group", "profile_picture", "created_at",
        ]


class EmployeeDetailSerializer(serializers.ModelSerializer):
    full_name            = serializers.CharField(read_only=True)
    designation_name     = serializers.CharField(source="designation_ref.name", read_only=True, default=None)
    department_name      = serializers.CharField(source="department_ref.name",  read_only=True, default=None)
    location_name        = serializers.CharField(source="location.name",        read_only=True, default=None)
    location_city        = serializers.CharField(source="location.city",        read_only=True, default=None)
    location_state       = serializers.CharField(source="location.state",       read_only=True, default=None)
    grade_name           = serializers.CharField(source="grade.name",           read_only=True, default=None)
    employment_type_name = serializers.CharField(source="employment_type.name", read_only=True, default=None)
    shift_category_name  = serializers.CharField(source="shift_category.name",  read_only=True, default=None)
    manager_name         = serializers.CharField(source="manager.full_name",    read_only=True, default=None)
    profile_picture_url  = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "keycloak_id", "username", "email",
            "first_name", "last_name", "full_name",
            "employee_code",
            "designation", "department",
            "designation_ref", "designation_name",
            "department_ref", "department_name",
            "location", "location_name", "location_city", "location_state",
            "grade", "grade_name",
            "employment_type", "employment_type_name",
            "joining_date", "retirement_date", "date_of_birth",
            "gender", "phone_number", "alternative_number", "address", "bio", "company",
            "total_experience", "prior_experience",
            "manager", "manager_name",
            "shift_applicable", "shift_category", "shift_category_name",
            "custom_shift_start", "custom_shift_end",
            "status", "is_active", "is_pmo", "is_manager", "is_staff",
            "keycloak_group", "profile_picture", "profile_picture_url",
            "created_at", "updated_at", "last_login",
        ]
        read_only_fields = ["id", "keycloak_id", "employee_code", "created_at", "updated_at", "last_login"]

    def get_profile_picture_url(self, obj):
        try:
            return obj.profile_picture.url if obj.profile_picture else None
        except Exception:
            return None


class EmployeeCreateSerializer(serializers.ModelSerializer):
    def validate_phone_number(self, value: str) -> str:
        return validate_phone(value, "Phone number")

    def validate_alternative_number(self, value: str) -> str:
        return validate_phone(value, "Alternative number")

    class Meta:
        model = Employee
        fields = [
            "username", "email", "first_name", "last_name",
            "phone_number", "alternative_number", "address",
            "gender", "date_of_birth",
            "designation_ref", "department_ref", "location",
            "grade", "employment_type",
            "joining_date", "date_of_birth",
            "prior_experience", "total_experience",
            "manager",
            "shift_applicable", "shift_category",
            "custom_shift_start", "custom_shift_end",
            "status", "keycloak_group", "company",
        ]
        extra_kwargs = {
            "username": {"required": False, "allow_blank": True},
        }


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    def validate_phone_number(self, value: str) -> str:
        return validate_phone(value, "Phone number")

    def validate_alternative_number(self, value: str) -> str:
        return validate_phone(value, "Alternative number")

    class Meta:
        model = Employee
        fields = [
            "first_name", "last_name",
            "designation", "department",
            "designation_ref", "department_ref", "location",
            "grade", "employment_type",
            "joining_date", "retirement_date", "date_of_birth",
            "gender", "phone_number", "alternative_number", "address", "bio", "company",
            "total_experience", "prior_experience",
            "manager",
            "shift_applicable", "shift_category",
            "custom_shift_start", "custom_shift_end",
            "status", "keycloak_group",
        ]


class EmployeeDropdownSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="full_name")
    value = serializers.UUIDField(source="id")
    designation_display = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["value", "label", "username", "email", "designation_display"]

    def get_designation_display(self, obj):
        if obj.designation_ref:
            return obj.designation_ref.name
        return obj.designation or ""


class EmployeeSearchSerializer(serializers.ModelSerializer):
    """Compact serializer for global search preview (Employment + Profile only)."""
    full_name            = serializers.CharField(read_only=True)
    designation_name     = serializers.CharField(source="designation_ref.name", read_only=True, default=None)
    department_name      = serializers.CharField(source="department_ref.name",  read_only=True, default=None)
    location_name        = serializers.CharField(source="location.name",        read_only=True, default=None)
    grade_name           = serializers.CharField(source="grade.name",           read_only=True, default=None)
    employment_type_name = serializers.CharField(source="employment_type.name", read_only=True, default=None)
    shift_category_name  = serializers.CharField(source="shift_category.name",  read_only=True, default=None)
    manager_name         = serializers.CharField(source="manager.full_name",    read_only=True, default=None)
    profile_picture_url  = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            # identity
            "id", "full_name", "first_name", "last_name",
            "employee_code", "email", "username",
            # employment
            "status", "designation_name", "department_name",
            "location_name", "grade_name", "employment_type_name",
            "joining_date", "total_experience", "prior_experience",
            "shift_applicable", "shift_category_name",
            "phone_number", "is_pmo", "is_manager", "is_staff",
            "keycloak_group", "manager_name", "company",
            # profile
            "gender", "date_of_birth", "bio",
            "profile_picture_url",
        ]

    def get_profile_picture_url(self, obj):
        try:
            return obj.profile_picture.url if obj.profile_picture else None
        except Exception:
            return None


class EmployeeCertificateSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        from .models import EmployeeCertificate
        model = EmployeeCertificate
        fields = [
            "id", "employee", "title", "issuing_organization",
            "issue_date", "expiry_date", "credential_id",
            "file", "file_url", "created_at",
        ]
        read_only_fields = ["file_url"]

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None
