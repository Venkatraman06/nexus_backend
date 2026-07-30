import os
import re

def resolve_conflict(filepath, resolver_func):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Regex to find conflict blocks
    pattern = re.compile(r'<<<<<<< HEAD\n(.*?)\n=======\n(.*?)\n>>>>>>> [a-f0-9]+', re.DOTALL)
    
    def replacer(match):
        head_content = match.group(1)
        develop_content = match.group(2)
        return resolver_func(filepath, head_content, develop_content)
        
    resolved_content = pattern.sub(replacer, content)
    
    with open(filepath, 'w') as f:
        f.write(resolved_content)

def custom_resolver(filepath, head, develop):
    if "apps/accounts/views.py" in filepath:
        # Keep head but replace bms. with pmt.
        return head.replace("bms.", "pmt.")
    elif "apps/followups/views.py" in filepath or "apps/meetings/views.py" in filepath or "apps/todos/views.py" in filepath:
        return head.replace("bms.", "pmt.")
    elif "apps/workspace/views.py" in filepath:
        if "permission_classes =" in head:
            # HEAD has HasKeycloakPermission, develop doesn't
            # We keep head but we change bms to pmt if needed
            return head.replace("bms.", "pmt.")
        else:
            return head.replace("bms.", "pmt.")
    return head.replace("bms.", "pmt.")

files = [
    "apps/accounts/views.py",
    "apps/followups/views.py",
    "apps/meetings/views.py",
    "apps/todos/views.py",
    "apps/workspace/views.py"
]

for f in files:
    resolve_conflict(f, custom_resolver)
    
print("Conflicts resolved.")
