import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.sales.models import TrainingCategory

def seed_sales_categories():
    print("Seeding standard Business/Training Categories...")
    TrainingCategory.objects.get_or_create(name="Corporate Training", defaults={"color": "#2563EB"})
    TrainingCategory.objects.get_or_create(name="Executive Coaching", defaults={"color": "#7C3AED"})
    TrainingCategory.objects.get_or_create(name="Technical Certification", defaults={"color": "#10B981"})
    TrainingCategory.objects.get_or_create(name="Consulting & Audit", defaults={"color": "#F59E0B"})
    print("Business Categories initialized cleanly.")

if __name__ == "__main__":
    seed_sales_categories()
