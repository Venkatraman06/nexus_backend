import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nexus_backend.settings")
django.setup()

from apps.payment.models import Invoice, Payment
from apps.crm.models import Client

payment = Payment.objects.filter(payment_reference="PAY-260001").first()
invoice = Invoice.objects.filter(invoice_number="INV-260002").first()

print("Payment Client:", payment.client.name, "ID:", payment.client.id)
print("Invoice Client:", invoice.client.name, "ID:", invoice.client.id)

