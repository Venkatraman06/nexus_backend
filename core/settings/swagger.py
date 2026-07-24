SPECTACULAR_SETTINGS = {
    "TITLE": "PMO Platform API",
    "DESCRIPTION": (
        "## Enterprise PMO & Mini Jira Platform\n\n"
        "Manage projects, epics, stories, work items, employee allocation, "
        "timesheets, and billing utilization.\n\n"
        "**Authentication:** All endpoints require a Keycloak Bearer token.\n"
        "Click **Authorize** and paste: `Bearer <your_access_token>`"
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "ENUM_NAME_OVERRIDES": {
        "ProjectStatusEnum":    "apps.common.constants.ProjectStatus",
        "ProjectHealthEnum":    "apps.common.constants.ProjectHealth",
        "WorkItemStatusEnum":   "apps.common.constants.WorkItemStatus",
        "WorkItemTypeEnum":     "apps.common.constants.WorkItemType",
        "WorkItemPriorityEnum": "apps.common.constants.WorkItemPriority",
        "EmployeeStatusEnum":   "apps.common.constants.EmployeeStatus",
        "BillingTypeEnum":      "apps.common.constants.BillingType",
        "BusinessTypeEnum":     "apps.common.constants.BusinessType",
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.common.swagger.postprocess_schema_tags",
    ],

    # Swagger UI settings
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "docExpansion": "none",
    },

    # Tags for grouping endpoints in the UI
    "TAGS": [
        {"name": "auth",        "description": "Employee & permission sync"},
        {"name": "projects",    "description": "Clients, Projects, Epics, Stories"},
        {"name": "workitems",   "description": "Work items (Task / Bug / CR) & attachments"},
        {"name": "timesheets",  "description": "Time logging & weekly summary"},
        {"name": "allocation",  "description": "Employee allocation & capacity planning"},
        {"name": "reports",     "description": "Portfolio, utilization & allocation reports"},
        {"name": "dashboard",   "description": "PMO dashboard KPIs"},
        {"name": "workflow",    "description": "Workflow states & transitions"},
    ],

    # Bearer token security scheme
    "SECURITY": [{"BearerAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Paste your Keycloak access token here.",
            }
        }
    },
}
