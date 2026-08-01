import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from rest_framework.test import APIClient
from apps.accounts.models import Employee
from apps.sales.models import TrainingCategory, Deal, Quotation
from apps.leads.models import Lead, Client

def test_sales_and_conversion():
    print("--- Running Sales & Lead-Client Conversion Tests ---")
    
    # 1. Setup superuser/admin user for test client
    user = Employee.objects.filter(is_superuser=True).first()
    if not user:
        user = Employee.objects.create_superuser(
            email="admin_test@example.com",
            username="admin_test",
            password="password123",
            first_name="Admin",
            last_name="Test"
        )
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    # 2. Test Training Categories endpoint
    res = client.get("/pmt/api/v1/training-categories/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    print("[PASS] GET /pmt/api/v1/training-categories/ passed:", len(res.data))

    # 3. Test Deals endpoint
    res = client.get("/pmt/api/v1/deals/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    print("[PASS] GET /pmt/api/v1/deals/ passed:", len(res.data))

    # 4. Test Quotations endpoint
    res = client.get("/pmt/api/v1/quotations/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.data}"
    print("[PASS] GET /pmt/api/v1/quotations/ passed:", len(res.data))

    # 5. Test Lead -> Client automatic conversion & undo
    lead = Lead.objects.create(
        name="Automated Test Lead",
        contact_person="Test Person",
        email="test_lead_conv@example.com",
        company="Test Automation Inc",
        status="LEAD"
    )
    print(f"Created Lead id={lead.id}, status=LEAD")

    # Patch status to WON with conversion form details
    patch_res = client.patch(
        f"/pmt/api/v1/leads/{lead.id}/",
        {
            "status": "WON",
            "deal_title": "Python Training Contract",
            "deal_amount": "50000.00",
            "deal_description": "Full-stack training for 30 developers"
        },
        format="json"
    )
    assert patch_res.status_code == 200, f"PATCH lead failed: {patch_res.data}"
    
    # Check if Client record was created
    converted_client = Client.objects.filter(email__iexact="test_lead_conv@example.com", is_deleted=False).first()
    assert converted_client is not None, "Client was NOT automatically created when lead status changed to WON!"
    assert "Auto-converted" in converted_client.notes, f"Notes missing Auto-converted badge info: {converted_client.notes}"
    print(f"[PASS] Lead status WON -> Auto-created Client id={converted_client.id}, notes={converted_client.notes}")

    # Check if Deal record was created in Sales
    converted_deal = Deal.objects.filter(client=converted_client, is_deleted=False).first()
    assert converted_deal is not None, "Deal was NOT automatically created in Sales when lead status changed to WON!"
    assert converted_deal.title == "Python Training Contract", f"Deal title mismatch: {converted_deal.title}"
    print(f"[PASS] Lead status WON -> Auto-created Sales Deal id={converted_deal.id}, title='{converted_deal.title}', val={converted_deal.expected_value}")

    # Patch status back to LEAD (undo conversion)
    undo_res = client.patch(f"/pmt/api/v1/leads/{lead.id}/", {"status": "LEAD"}, format="json")
    assert undo_res.status_code == 200, f"Undo lead status failed: {undo_res.data}"

    converted_client_check = Client.objects.filter(id=converted_client.id, is_deleted=False).first()
    assert converted_client_check is None, "Auto-created client record was NOT deleted on status revert!"
    
    converted_deal_check = Deal.objects.filter(id=converted_deal.id, is_deleted=False).first()
    assert converted_deal_check is None, "Auto-created sales deal record was NOT deleted on status revert!"
    print("[PASS] Reverting lead status -> Auto-created Client & Sales Deal correctly removed!")

    print("\n--- All Backend Sales & Conversion Tests Passed Successfully! ---")

if __name__ == "__main__":
    test_sales_and_conversion()
