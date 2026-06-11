from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "packages.workflow"
    label = "pmt_workflow"
    verbose_name = "Workflow"
