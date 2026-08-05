import re

with open('apps/accounts/models.py', 'r') as f:
    content = f.read()

content = content.replace('class EmployeeManager(BaseUserManager):', '''class BaseEmployeeManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def generate_employee_code(self):
        codes = (
            self.model.base_objects.filter(employee_code__startswith="HIT-")
            .values_list("employee_code", flat=True)
        )
        nums = []
        for code in codes:
            try:
                nums.append(int(code[4:]))
            except (ValueError, IndexError):
                pass
        num = max(nums) + 1 if nums else 1
        return f"HIT-{num:03d}"

class EmployeeManager(BaseEmployeeManager):''')

content = content.replace('base_objects = models.Manager()', 'base_objects = BaseEmployeeManager()')

# Also remove the duplicate generate_employee_code from EmployeeManager if it exists.
# We already added it in BaseEmployeeManager, so we need to remove the one in EmployeeManager.
content = re.sub(r'    def generate_employee_code\(self\):.*?return f"HIT-\{num:03d\}"\n', '', content, flags=re.DOTALL)

with open('apps/accounts/models.py', 'w') as f:
    f.write(content)
