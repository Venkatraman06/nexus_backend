from django.db.models import Prefetch
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.common.permissions import HasKeycloakPermission, IsAuthenticated
from apps.common.viewsets import BaseModelViewSet
from packages.workflow.exceptions import WorkflowTransitionError

from .filters import SocialPostFilter
from .models import SocialPost, SocialPostComment, SocialPostLike
from .workflow import (
    assign_initial_state,
    ensure_social_post_workflow,
    get_allowed_destination_slugs,
    proceed_social_post,
)
from .serializers import (
    SocialPostCreateSerializer,
    SocialPostDetailSerializer,
    SocialPostListSerializer,
    SocialPostTransitionSerializer,
)


class SocialPostViewSet(BaseModelViewSet):
    queryset = SocialPost.objects.select_related(
        "created_by", "workflow_state",
    ).prefetch_related(
        Prefetch(
            "comments",
            queryset=SocialPostComment.objects.select_related("created_by").order_by("created_at"),
        ),
    ).filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    filterset_class = SocialPostFilter
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "title", "like_count"]
    ordering = ["-created_at"]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    PERMISSION_MAP = {
        "list":           "pmt.social_feed.view",
        "retrieve":       "pmt.social_feed.view",
        "create":         "pmt.social_feed.create",
        "update":         "pmt.social_feed.update",
        "partial_update": "pmt.social_feed.update",
        "destroy":        "pmt.social_feed.delete",
        "transition":     "pmt.social_feed.transition",
        "like":           "pmt.social_feed.view",
        "comment":        "pmt.social_feed.view",
        "feed":           "pmt.social_feed.view",
        "my_posts":       "pmt.social_feed.view",
    }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SocialPostDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return SocialPostCreateSerializer
        return SocialPostListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def _user_can_manage(self) -> bool:
        user = self.request.user
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        user_perms = getattr(self.request, "user_permissions", [])
        return "pmt.social_feed.manage" in user_perms

    def list(self, request, *args, **kwargs):
        ensure_social_post_workflow()
        for post in self.filter_queryset(self.get_queryset()):
            assign_initial_state(post)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        ensure_social_post_workflow()
        user = self.request.user
        post = serializer.save(
            created_by=user,
            updated_by=user,
            created_by_name=user.full_name if hasattr(user, "full_name") else str(user),
        )
        assign_initial_state(post)

        # Admin/HR creators can publish directly by default
        if self._user_can_manage():
            from .workflow import proceed_social_post
            try:
                proceed_social_post(post, user=user, destination_slug="published")
                post.refresh_from_db()
                from .notifications import publish_social_post_published
                publish_social_post_published(post, actor_id=str(user.pk))
            except WorkflowTransitionError:
                pass
        else:
            # Regular user — submit for approval
            try:
                from .workflow import proceed_social_post
                proceed_social_post(post, user=user, destination_slug="pending_approval")
                post.refresh_from_db()
                from .notifications import publish_social_post_pending_approval
                publish_social_post_pending_approval(post, actor_id=str(user.pk))
            except WorkflowTransitionError:
                pass

    def perform_update(self, serializer):
        ensure_social_post_workflow()
        user = self.request.user
        post = serializer.save(updated_by=user)
        assign_initial_state(post)
        post.refresh_from_db()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Only creator or admin can delete
        uid = request.user.pk
        is_admin = self._user_can_manage()
        if instance.created_by_id != uid and not is_admin:
            return Response(
                {"detail": "You do not have permission to delete this post."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Feed ──────────────────────────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="feed")
    def feed(self, request):
        """Only published posts, ordered by creation date."""
        ensure_social_post_workflow()
        qs = self.get_queryset().filter(
            workflow_state__slug="published",
            is_company_wide=True,
        )
        qs = self.filter_queryset(qs)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    # ── My Posts ──────────────────────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="my-posts")
    def my_posts(self, request):
        """Posts created by the current user."""
        ensure_social_post_workflow()
        qs = super().get_queryset().filter(created_by=request.user)
        for post in qs:
            assign_initial_state(post)
        qs = self.filter_queryset(qs)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    # ── Like / Unlike ─────────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="like")
    def like(self, request, pk=None):
        post = self.get_object()
        user = request.user
        like, created = SocialPostLike.objects.get_or_create(
            post=post, created_by=user,
            defaults={"updated_by": user},
        )
        if not created:
            like.delete()
            post.like_count = max(0, post.like_count - 1)
        else:
            post.like_count = SocialPostLike.objects.filter(post=post).count()

        post.save(update_fields=["like_count"])
        return Response({
            "liked": created,
            "like_count": post.like_count,
        })

    # ── Comment ───────────────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="comment")
    def comment(self, request, pk=None):
        post = self.get_object()
        content = request.data.get("content", "").strip()
        if not content:
            return Response(
                {"error": "Comment content is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comment = SocialPostComment.objects.create(
            post=post,
            created_by=request.user,
            updated_by=request.user,
            content=content,
        )
        post.comment_count = SocialPostComment.objects.filter(post=post).count()
        post.save(update_fields=["comment_count"])

        from .serializers import SocialPostCommentSerializer
        return Response(
            SocialPostCommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )

    # ── Transition ────────────────────────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        ensure_social_post_workflow()
        post = self.get_object()

        serializer = SocialPostTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        destination_slug = serializer.validated_data["destination_state"]
        comments = serializer.validated_data.get("comments", "")

        # Check if the user is allowed to perform this transition
        user_perms = getattr(request, "user_permissions", [])
        allowed = get_allowed_destination_slugs(post, request.user, permissions=user_perms)
        if destination_slug not in allowed:
            raise PermissionDenied(
                f"You are not allowed to transition this post to '{destination_slug}'."
            )

        try:
            proceeding = proceed_social_post(
                post,
                user=request.user,
                destination_slug=destination_slug,
                comments=comments,
            )
        except WorkflowTransitionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        post.refresh_from_db()

        # If published, notify all employees
        if destination_slug == "published":
            from .notifications import publish_social_post_published
            publish_social_post_published(post, actor_id=str(request.user.pk))

        return Response({
            "message": "Status transitioned successfully.",
            "workflow_state_name": post.workflow_state.name if post.workflow_state else None,
            "workflow_state_slug": post.workflow_state.slug if post.workflow_state else None,
            "workflow_state_color": post.workflow_state.color_code if post.workflow_state else None,
        })
