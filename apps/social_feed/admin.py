from django.contrib import admin

from .models import SocialPost, SocialPostComment, SocialPostLike


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by_name", "like_count", "comment_count", "workflow_state", "is_company_wide", "is_active")
    list_filter = ("workflow_state", "is_company_wide", "is_active")
    search_fields = ("title", "content")
    readonly_fields = ("like_count", "comment_count", "created_by_name")


@admin.register(SocialPostLike)
class SocialPostLikeAdmin(admin.ModelAdmin):
    list_display = ("post", "created_by")
    list_filter = ("post",)


@admin.register(SocialPostComment)
class SocialPostCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "content", "created_by", "created_at")
    list_filter = ("post",)
