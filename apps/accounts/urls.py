from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import EmployeeViewSet, EmployeeSyncView, EmployeeSimpleDropdownView, EmployeeCertificateViewSet, KeycloakGroupsView, MeView, OrgTreeView, EmployeeSearchView
from .permission_views import PermissionSyncView, PermissionCreateView
from .role_views import PermissionCatalogView, RoleListView, RoleDetailView, RolePermissionsUpdateView
from .auth_views import (
    TokenView, TokenRefreshView, LogoutView, ForgotPasswordView,
    VerifyResetOtpView, ValidateResetTokenView, ResetPasswordView, OnboardSetPasswordView,
)

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("employee-certificates", EmployeeCertificateViewSet, basename="employee-certificate")

# Named / action paths MUST come before router.urls so the router's
# generic  employees/<pk>/  pattern does not swallow them first.
urlpatterns = [
    # ── Authentication (public) ───────────────────────────
    path("auth/token/",           TokenView.as_view(),         name="auth-token"),
    path("auth/token/refresh/",   TokenRefreshView.as_view(),  name="auth-token-refresh"),
    path("auth/logout/",          LogoutView.as_view(),        name="auth-logout"),
    path("auth/forgot-password/",         ForgotPasswordView.as_view(),       name="auth-forgot-password"),
    path("auth/forgot-password/verify/",    VerifyResetOtpView.as_view(),       name="auth-forgot-password-verify"),
    path("auth/reset-password/",            ResetPasswordView.as_view(),        name="auth-reset-password"),
    path("auth/reset-password/validate/",   ValidateResetTokenView.as_view(),   name="auth-reset-password-validate"),
    path("auth/onboard/set-password/",      OnboardSetPasswordView.as_view(),   name="auth-onboard-set-password"),

    # ── Employee action endpoints (before router to avoid pk conflict) ─
    path("employees/org-tree/",       OrgTreeView.as_view(),           name="org-tree"),
    path("employees/sync/keycloak/",  EmployeeSyncView.as_view(),      name="employee-sync"),
    path("employees/search/",         EmployeeSearchView.as_view(),    name="employee-search"),
    path("employees/simple-dropdown/", EmployeeSimpleDropdownView.as_view(), name="employee-simple-dropdown"),

    # ── Current user ──────────────────────────────────────
    path("users/me/",        MeView.as_view(),             name="users-me"),

    # ── Keycloak groups ────────────────────────────────────
    path("keycloak-groups/", KeycloakGroupsView.as_view(), name="keycloak-groups"),

    # ── Permission management ──────────────────────────────
    path("permissions/catalog/", PermissionCatalogView.as_view(), name="permission-catalog"),
    path("permissions/create/",  PermissionCreateView.as_view(),  name="permission-create"),
    path("permissions/sync/",    PermissionSyncView.as_view(),    name="permission-sync"),

    # ── Role management (Keycloak groups) ─────────────────
    path("roles/",                              RoleListView.as_view(),              name="role-list"),
    path("roles/<str:group_id>/",               RoleDetailView.as_view(),            name="role-detail"),
    path("roles/<str:group_id>/permissions/",   RolePermissionsUpdateView.as_view(), name="role-permissions"),
] + router.urls



