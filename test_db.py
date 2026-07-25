from apps.meetings.models import Meeting
from apps.followups.models import FollowUp

print(f"Meetings count: {Meeting.objects.count()}")
print(f"Followups count: {FollowUp.objects.count()}")

for m in Meeting.objects.all()[:5]:
    print(f"Meeting: {m.title}")

for f in FollowUp.objects.all()[:5]:
    print(f"Followup: {f.title} (type: {f.type})")
