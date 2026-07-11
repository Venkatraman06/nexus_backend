import os
import django
from datetime import date, time, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.accounts.models import Employee
from apps.todos.models import Todo
from apps.todos.workflow import ensure_todo_workflow, assign_initial_state
from packages.workflow.models import State
from django.contrib.contenttypes.models import ContentType

def seed():
    # Make sure workflow states are seeded
    ensure_todo_workflow()

    # Clear existing todos to start fresh
    Todo.objects.all().delete()
    print("Deleted existing todos.")

    employees = list(Employee.objects.all())
    if not employees:
        print("No employees found. Seed main demo data first.")
        return

    ceo = Employee.objects.filter(username='ceo@hackersinfotech.com').first() or employees[0]
    hit1 = Employee.objects.filter(username='HIT-001').first() or employees[0]
    hit9 = Employee.objects.filter(username='HIT-009').first() or employees[0]

    ct = ContentType.objects.get_for_model(Todo)
    state_open = State.objects.get(content_type=ct, slug='open')
    state_inprogress = State.objects.get(content_type=ct, slug='inprogress')
    state_done = State.objects.get(content_type=ct, slug='done')

    today = date.today()

    todos_data = [
        {
            "title": "Prepare sprint review presentation",
            "description": "Prepare slides for the sprint 5 review highlighting PMT and CRM updates.",
            "priority": "HIGH",
            "due_date": today,
            "start_time": time(10, 0),
            "end_time": time(11, 30),
            "state": state_inprogress,
            "reporter": ceo,
            "assignees": [hit1, hit9]
        },
        {
            "title": "Review database index performance",
            "description": "Investigate query latency on workspace calendar views and add indexes.",
            "priority": "MEDIUM",
            "due_date": today + timedelta(days=1),
            "start_time": time(14, 0),
            "end_time": time(15, 0),
            "state": state_open,
            "reporter": hit1,
            "assignees": [hit1]
        },
        {
            "title": "Design new dashboard layout",
            "description": "Design mockups for Jira/Zoho style dashboard cards and side navigation.",
            "priority": "HIGH",
            "due_date": today + timedelta(days=2),
            "start_time": time(9, 0),
            "end_time": time(11, 0),
            "state": state_open,
            "reporter": ceo,
            "assignees": [hit1, hit9]
        },
        {
            "title": "Fix Keycloak session timeout issue",
            "description": "Resolve token expiration loop happening in dev environment.",
            "priority": "HIGH",
            "due_date": today - timedelta(days=1),
            "start_time": time(11, 0),
            "end_time": time(12, 0),
            "state": state_done,
            "reporter": hit9,
            "assignees": [hit9]
        },
        {
            "title": "Write unit tests for authentication view",
            "description": "Ensure password reset logic is covered with pytest cases.",
            "priority": "LOW",
            "due_date": today + timedelta(days=3),
            "start_time": time(16, 0),
            "end_time": time(17, 30),
            "state": state_open,
            "reporter": hit1,
            "assignees": [hit9]
        },
        {
            "title": "Weekly project sync",
            "description": "Sync up with PMO regarding delivery timeline overrides.",
            "priority": "MEDIUM",
            "due_date": today,
            "start_time": time(15, 30),
            "end_time": time(16, 30),
            "state": state_inprogress,
            "reporter": ceo,
            "assignees": [ceo, hit1, hit9]
        },
        {
            "title": "Update API documentation",
            "description": "Document newly created calendar date-range query filters.",
            "priority": "LOW",
            "due_date": today + timedelta(days=5),
            "start_time": None,
            "end_time": None,
            "state": state_open,
            "reporter": hit1,
            "assignees": [hit1]
        },
        {
            "title": "Optimize minified production bundle",
            "description": "Analyze Rollup chunks and split vendor dependencies.",
            "priority": "MEDIUM",
            "due_date": today - timedelta(days=2),
            "start_time": time(10, 0),
            "end_time": time(11, 0),
            "state": state_done,
            "reporter": hit9,
            "assignees": [hit1]
        }
    ]

    for data in todos_data:
        todo = Todo.objects.create(
            title=data["title"],
            description=data["description"],
            priority=data["priority"],
            due_date=data["due_date"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            workflow_state=data["state"],
            reporter=data["reporter"]
        )
        todo.assignees.set(data["assignees"])
        print(f"Created Todo: {todo.title}")

if __name__ == '__main__':
    seed()
