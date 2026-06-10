from rest_framework import serializers

from .models import SocialPost, SocialPostComment


class SocialPostCommentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = SocialPostComment
        fields = ["id", "post", "content", "created_by", "created_by_name", "created_at"]
        read_only_fields = ["created_by", "created_by_name"]


class SocialPostListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    created_by_avatar = serializers.SerializerMethodField()
    created_by_id = serializers.SerializerMethodField()
    is_liked_by_me = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")
    can_transition = serializers.SerializerMethodField()
    allowed_destination_slugs = serializers.SerializerMethodField()
    comments = SocialPostCommentSerializer(many=True, read_only=True)

    class Meta:
        model = SocialPost
        fields = [
            "id", "title", "content", "image_url", "attachment_url", "attachment_name",
            "created_by", "created_by_id", "created_by_name", "created_by_avatar",
            "is_company_wide", "like_count", "comment_count",
            "is_liked_by_me", "comments",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "can_transition", "allowed_destination_slugs",
            "created_at", "updated_at",
        ]

    def get_created_by_name(self, obj):
        return obj.created_by_name or (obj.created_by.full_name if obj.created_by else "")

    def get_created_by_id(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else None

    def get_created_by_avatar(self, obj):
        if obj.created_by and obj.created_by.profile_picture:
            try:
                return obj.created_by.profile_picture.url
            except Exception:
                return None
        return None

    def get_image_url(self, obj):
        if obj.image:
            try:
                return obj.image.url
            except Exception:
                return None
        return None

    def get_attachment_url(self, obj):
        if obj.attachment:
            try:
                return obj.attachment.url
            except Exception:
                return None
        return None

    def get_attachment_name(self, obj):
        if obj.attachment:
            try:
                import os
                return os.path.basename(obj.attachment.name)
            except Exception:
                return "Attachment"
        return None

    def get_is_liked_by_me(self, obj):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return False
        return obj.likes.filter(created_by=request.user).exists()

    def get_can_transition(self, obj):
        request = self.context.get("request")
        if not request or not request.user:
            return False
        user = request.user
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        user_perms = getattr(request, "user_permissions", [])
        if "pmt.social_feed.manage" in user_perms:
            return True
        # Creator can transition their own posts
        uid = user.pk
        return obj.created_by_id == uid

    def get_allowed_destination_slugs(self, obj):
        request = self.context.get("request")
        if not request or not request.user:
            return []
        try:
            from .workflow import get_allowed_destination_slugs as _allowed_slugs
            user_perms = getattr(request, "user_permissions", [])
            return _allowed_slugs(obj, request.user, permissions=user_perms)
        except Exception:
            return []


class SocialPostDetailSerializer(SocialPostListSerializer):
    available_states = serializers.SerializerMethodField()

    class Meta(SocialPostListSerializer.Meta):
        fields = SocialPostListSerializer.Meta.fields + ["available_states"]

    def get_available_states(self, obj):
        try:
            states = obj.get_available_next_states()
            return [
                {"id": str(s.id), "name": s.name, "slug": s.slug, "color": s.color_code}
                for s in states
            ]
        except Exception:
            return []


class SocialPostCreateSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    attachment = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = SocialPost
        fields = ["title", "content", "image", "attachment", "is_company_wide"]


class SocialPostTransitionSerializer(serializers.Serializer):
    destination_state = serializers.CharField(required=True)
    comments = serializers.CharField(required=False, default="", allow_blank=True)
