from rest_framework import serializers

from .models import Ticket, TicketAttachment, TicketComment, TicketHistory
from .validators import validate_ticket_against_project, validate_ticket_attachment_file


class TicketAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = [
            "id", "file", "file_url", "file_name", "file_size",
            "content_type", "uploaded_by", "uploaded_at",
        ]
        read_only_fields = [
            "id", "file_url", "file_name", "file_size",
            "content_type", "uploaded_by", "uploaded_at",
        ]

    def validate_file(self, file):
        validate_ticket_attachment_file(file)
        return file

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None

    def create(self, validated_data):
        file = validated_data.get("file")
        if file:
            validated_data.setdefault("file_name", file.name)
            validated_data.setdefault("file_size", file.size)
            validated_data.setdefault("content_type", getattr(file, "content_type", ""))
        return super().create(validated_data)


class TicketCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_avatar = serializers.SerializerMethodField()

    class Meta:
        model = TicketComment
        fields = [
            "id", "ticket", "author", "author_name", "author_avatar",
            "body", "is_edited", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "ticket", "author", "author_name", "author_avatar",
            "is_edited", "created_at", "updated_at",
        ]
        extra_kwargs = {
            "body": {"required": True, "allow_blank": False},
        }

    def get_author_name(self, obj):
        return obj.author.full_name if obj.author else None

    def get_author_avatar(self, obj):
        if not obj.author:
            return None
        try:
            return obj.author.profile_picture.url if obj.author.profile_picture else None
        except Exception:
            return None


class TicketHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TicketHistory
        fields = ["id", "action", "changes", "changed_by_name", "changed_at"]

    def get_changed_by_name(self, obj):
        return obj.changed_by.full_name if obj.changed_by else "System"


class TicketListSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True)
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")
    parent_ticket_id = serializers.CharField(source="parent.ticket_id", read_only=True, default=None)
    children_count = serializers.SerializerMethodField()
    logged_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "ticket_id", "title", "type", "priority",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "project", "project_name", "project_code",
            "assignee", "assignee_name", "reporter", "reporter_name",
            "parent", "parent_ticket_id", "children_count",
            "due_date", "original_estimate", "logged_hours",
            "approved", "created_at",
        ]

    def get_assignee_name(self, obj):
        return obj.assignee.full_name if obj.assignee else None

    def get_reporter_name(self, obj):
        return obj.reporter.full_name if obj.reporter else None

    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class TicketDetailSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True)
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")
    available_states = serializers.SerializerMethodField()
    parent_ticket_id = serializers.CharField(source="parent.ticket_id", read_only=True, default=None)
    parent_title = serializers.CharField(source="parent.title", read_only=True, default=None)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    notify_users_info = serializers.SerializerMethodField()
    logged_hours = serializers.FloatField(read_only=True)
    remaining_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id", "ticket_id", "title", "description", "type", "priority",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "available_states",
            "project", "project_name", "project_code",
            "assignee", "assignee_name", "reporter", "reporter_name",
            "parent", "parent_ticket_id", "parent_title",
            "due_date", "original_estimate", "logged_hours", "remaining_hours",
            "approved", "notify_users", "notify_users_info",
            "attachments",
            "created_at", "updated_at",
        ]

    def get_assignee_name(self, obj):
        return obj.assignee.full_name if obj.assignee else None

    def get_reporter_name(self, obj):
        return obj.reporter.full_name if obj.reporter else None

    def get_available_states(self, obj):
        try:
            states = obj.get_available_next_states()
            return [{"id": str(s.id), "name": s.name, "slug": s.slug, "color": s.color_code} for s in states]
        except Exception:
            return []

    def get_notify_users_info(self, obj):
        return [
            {"id": str(u.id), "name": u.full_name}
            for u in obj.notify_users.all()
        ]


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            "project", "title", "description", "type", "priority",
            "assignee", "reporter", "due_date", "original_estimate",
            "parent", "approved", "notify_users",
        ]

    def validate(self, data):
        project = data.get("project") or (self.instance.project if self.instance else None)

        if self.instance:
            if "due_date" in data:
                validate_ticket_against_project(project=project, due_date=data.get("due_date"))
            if "original_estimate" in data:
                validate_ticket_against_project(
                    project=project,
                    original_estimate=data.get("original_estimate"),
                )
        else:
            validate_ticket_against_project(
                project=project,
                due_date=data.get("due_date"),
                original_estimate=data.get("original_estimate"),
            )
        return data

    def create(self, validated_data):
        notify_users = validated_data.pop("notify_users", [])
        ticket = super().create(validated_data)
        if notify_users:
            ticket.notify_users.set(notify_users)
        return ticket

    def update(self, instance, validated_data):
        notify_users = validated_data.pop("notify_users", None)
        ticket = super().update(instance, validated_data)
        if notify_users is not None:
            ticket.notify_users.set(notify_users)
        return ticket


class TicketTransitionSerializer(serializers.Serializer):
    destination_state = serializers.CharField(required=True)
    comments = serializers.CharField(required=False, default="", allow_blank=True)
