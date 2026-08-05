from apps.followups.models import FollowUp
from apps.meetings.models import Meeting
import copy

followups = FollowUp.objects.filter(type="MEETING")
print(f"Found {followups.count()} followups with type MEETING")

for f in followups:
    # Check if a meeting with same id exists
    if Meeting.objects.filter(id=f.id).exists():
        continue
    
    m = Meeting(
        id=f.id,
        created_at=f.created_at,
        updated_at=f.updated_at,
        title=f.title,
        priority=f.priority,
        description=f.description,
        content=f.content,
        comments=f.comments,
        reporter=f.reporter,
        start_date=f.start_date,
        end_date=f.end_date,
        start_time=f.start_time,
        end_time=f.end_time,
        meeting_mode=f.meeting_mode,
        is_deleted=f.is_deleted,
        created_by=f.created_by,
        updated_by=f.updated_by
    )
    m.save()
    
    # Many to many
    for a in f.assignees.all():
        m.assignees.add(a)
    
    # State
    from packages.workflow.models import State
    if f.workflow_state:
        state_name = f.workflow_state.name
        # Find matching state for meeting
        state = State.objects.filter(workflow_type="MEETING", name=state_name).first()
        if state:
            m.workflow_state = state
            m.save()
        else:
            state = State.objects.filter(workflow_type="MEETING", is_initial=True).first()
            if state:
                m.workflow_state = state
                m.save()
            else:
                from apps.meetings.workflow import ensure_meeting_workflow, assign_initial_state
                ensure_meeting_workflow()
                assign_initial_state(m)

print(f"Meetings table now has {Meeting.objects.count()} records.")
