"""
Seed the PMT workflow configurations:
  1. Workflow Groups (PMO Team, Project Managers, Dev Team, QA Team)
  2. Project lifecycle workflow  : Proposal → Kickoff → Ongoing → UAT/Go-Live → AMC
  3. Work Item workflow          : Open → In Progress → In Review → Done → Closed / Blocked
"""
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from packages.workflow.models import WorkflowGroup, State, Transition


GROUPS = [
    {"name": "PMO Team",         "description": "Project Management Office members"},
    {"name": "Project Managers", "description": "Project Managers"},
    {"name": "Dev Team",         "description": "Developers and engineers"},
    {"name": "QA Team",          "description": "Quality Assurance team"},
]

PROJECT_STATES = [
    {"name": "Proposal",    "slug": "proposal",    "color_code": "#8B5CF6", "order": 1, "is_initial": True,  "is_final": False},
    {"name": "Kickoff",     "slug": "kickoff",     "color_code": "#3B82F6", "order": 2, "is_initial": False, "is_final": False},
    {"name": "Ongoing",     "slug": "ongoing",     "color_code": "#10B981", "order": 3, "is_initial": False, "is_final": False},
    {"name": "UAT/Go-Live", "slug": "uat-go-live", "color_code": "#F59E0B", "order": 4, "is_initial": False, "is_final": False},
    {"name": "AMC",         "slug": "amc",         "color_code": "#6366F1", "order": 5, "is_initial": False, "is_final": True},
]

PROJECT_TRANSITIONS = [
    ("proposal",    "kickoff",     "Approve & Kick Off",   ["PMO Team"],                    {"source": {"x": 50, "y": 100},  "destination": {"x": 250, "y": 100}}),
    ("kickoff",     "ongoing",     "Start Development",    ["PMO Team", "Project Managers"], {"source": {"x": 250, "y": 100}, "destination": {"x": 450, "y": 100}}),
    ("ongoing",     "uat-go-live", "Deploy to UAT",        ["PMO Team", "Project Managers"], {"source": {"x": 450, "y": 100}, "destination": {"x": 650, "y": 100}}),
    ("uat-go-live", "amc",         "Go Live → AMC",        ["PMO Team"],                    {"source": {"x": 650, "y": 100}, "destination": {"x": 850, "y": 100}}),
    ("ongoing",     "kickoff",     "Rollback",             ["PMO Team"],                    {"source": {"x": 450, "y": 200}, "destination": {"x": 250, "y": 200}}),
    ("uat-go-live", "ongoing",     "Failed UAT",           ["PMO Team", "Project Managers"], {"source": {"x": 650, "y": 200}, "destination": {"x": 450, "y": 200}}),
]

WORKITEM_STATES = [
    {"name": "Open",        "slug": "open",        "color_code": "#6B7280", "order": 1, "is_initial": True,  "is_final": False},
    {"name": "In Progress", "slug": "in-progress", "color_code": "#3B82F6", "order": 2, "is_initial": False, "is_final": False},
    {"name": "In Review",   "slug": "in-review",   "color_code": "#F59E0B", "order": 3, "is_initial": False, "is_final": False},
    {"name": "Done",        "slug": "done",        "color_code": "#10B981", "order": 4, "is_initial": False, "is_final": True},
    {"name": "Closed",      "slug": "closed",      "color_code": "#374151", "order": 5, "is_initial": False, "is_final": True},
    {"name": "Blocked",     "slug": "blocked",     "color_code": "#EF4444", "order": 6, "is_initial": False, "is_final": False},
]

WORKITEM_TRANSITIONS = [
    ("open",        "in-progress", "Start",        ["Dev Team", "Project Managers"],              {"source": {"x": 50, "y": 100},  "destination": {"x": 250, "y": 100}}),
    ("in-progress", "in-review",   "Submit Review","Dev Team",                                    {"source": {"x": 250, "y": 100}, "destination": {"x": 450, "y": 100}}),
    ("in-review",   "done",        "Approve",      ["QA Team", "Project Managers"],               {"source": {"x": 450, "y": 100}, "destination": {"x": 650, "y": 100}}),
    ("in-review",   "in-progress", "Reject",       ["QA Team", "Project Managers"],               {"source": {"x": 450, "y": 200}, "destination": {"x": 250, "y": 200}}),
    ("done",        "closed",      "Close",        ["PMO Team", "Project Managers"],              {"source": {"x": 650, "y": 100}, "destination": {"x": 850, "y": 100}}),
    ("open",        "blocked",     "Block",        ["Dev Team", "Project Managers", "PMO Team"],  {"source": {"x": 50,  "y": 200}, "destination": {"x": 50,  "y": 350}}),
    ("in-progress", "blocked",     "Block",        ["Dev Team", "Project Managers", "PMO Team"],  {"source": {"x": 250, "y": 200}, "destination": {"x": 50,  "y": 350}}),
    ("blocked",     "open",        "Unblock",      ["Dev Team", "Project Managers", "PMO Team"],  {"source": {"x": 50,  "y": 350}, "destination": {"x": 50,  "y": 200}}),
    ("done",        "in-progress", "Reopen",       ["PMO Team", "Project Managers"],              {"source": {"x": 650, "y": 200}, "destination": {"x": 250, "y": 200}}),
]


class Command(BaseCommand):
    help = "Seed workflow groups, states and transitions for Project and WorkItem"

    def handle(self, *args, **options):
        groups_map = self._seed_groups()
        self._seed_workflow(
            "projects", "project",
            PROJECT_STATES, PROJECT_TRANSITIONS, groups_map,
        )
        self._seed_workflow(
            "workitems", "workitem",
            WORKITEM_STATES, WORKITEM_TRANSITIONS, groups_map,
        )
        self.stdout.write(self.style.SUCCESS("\nWorkflow seeding complete."))

    def _seed_groups(self):
        groups_map = {}
        for g in GROUPS:
            obj, created = WorkflowGroup.objects.get_or_create(
                name=g["name"],
                defaults={"description": g["description"], "slug": slugify(g["name"])},
            )
            groups_map[g["name"]] = obj
            self.stdout.write(f"  {'Created' if created else 'Exists '} group: {obj.name}")
        return groups_map

    def _seed_workflow(self, app_label, model_name, states_cfg, transitions_cfg, groups_map):
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"ContentType {app_label}.{model_name} not found"))
            return

        self.stdout.write(f"\nSeeding {app_label}.{model_name} workflow...")

        state_map = {}
        for cfg in states_cfg:
            obj, created = State.objects.get_or_create(
                content_type=ct, slug=cfg["slug"],
                defaults={
                    "name":       cfg["name"],
                    "color_code": cfg["color_code"],
                    "order":      cfg["order"],
                    "is_initial": cfg["is_initial"],
                    "is_final":   cfg["is_final"],
                    "label":      cfg["name"],
                },
            )
            if not created:
                State.objects.filter(pk=obj.pk).update(
                    color_code=cfg["color_code"],
                    order=cfg["order"],
                    is_initial=cfg["is_initial"],
                    is_final=cfg["is_final"],
                )
            state_map[cfg["slug"]] = obj
            self.stdout.write(f"  {'Created' if created else 'Exists '} state: {obj.name}")

        for item in transitions_cfg:
            src_slug, dst_slug, label = item[0], item[1], item[2]
            group_names = item[3] if isinstance(item[3], list) else [item[3]]
            position = item[4]

            src = state_map.get(src_slug)
            dst = state_map.get(dst_slug)
            if not src or not dst:
                self.stdout.write(self.style.WARNING(
                    f"  Skipping {src_slug}→{dst_slug}: state not found"
                ))
                continue

            t, created = Transition.objects.get_or_create(
                content_type=ct, source_state=src, destination_state=dst,
                defaults={"label": label, "position": position},
            )
            if not created:
                t.label = label
                t.position = position
                t.save(update_fields=["label", "position"])

            allowed_groups = [groups_map[n] for n in group_names if n in groups_map]
            t.groups.set(allowed_groups)
            self.stdout.write(
                f"  {'Created' if created else 'Updated'} transition: "
                f"{src.name} → {dst.name}  [{', '.join(group_names)}]"
            )
