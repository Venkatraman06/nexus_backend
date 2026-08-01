import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.sales.models import Deal, Quotation
from apps.leads.models import Client, Lead

def clear_mock_data():
    print("Clearing mock/seed data from Sales and Client modules...")
    
    # 1. Delete seed deals
    dummy_titles = [
        "Python & Django Corporate Workshop",
        "Leadership Coaching Program",
        "Cloud Architecture Certification"
    ]
    deleted_deals, _ = Deal.objects.filter(title__in=dummy_titles).delete()
    print(f"Deleted {deleted_deals} mock deal records.")

    # 2. Delete seed clients
    dummy_client_names = [
        "TechCorp India",
        "Global Solutions"
    ]
    deleted_clients, _ = Client.objects.filter(name__in=dummy_client_names).delete()
    print(f"Deleted {deleted_clients} mock client records.")

    # 3. Delete mock quotations that belong to deleted/dummy clients
    deleted_quotes, _ = Quotation.objects.filter(client__isnull=True).delete()
    print(f"Deleted {deleted_quotes} orphan/mock quotation records.")

    print("Sales and Client modules cleaned successfully! Only real leads & converted opportunities remain.")

if __name__ == "__main__":
    clear_mock_data()
