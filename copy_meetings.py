import os

def replace_in_file(src, dest):
    if not os.path.exists(src):
        return
    with open(src, 'r') as f:
        content = f.read()

    # Replacements
    content = content.replace('FollowUp', 'Meeting')
    content = content.replace('Follow-up', 'Meeting')
    content = content.replace('followup', 'meeting')
    content = content.replace('FOLLOWUP', 'MEETING')
    content = content.replace('crm_followup', 'crm_meeting')
    
    with open(dest, 'w') as f:
        f.write(content)

base_src = '/home/dharshini/Desktop/nexus_test/nexus_backend/apps/followups/'
base_dest = '/home/dharshini/Desktop/nexus_test/nexus_backend/apps/meetings/'

files_to_copy = ['workflow.py', 'filters.py', 'urls.py', 'serializers.py', 'views.py', 'notifications.py']

for f in files_to_copy:
    replace_in_file(base_src + f, base_dest + f)

