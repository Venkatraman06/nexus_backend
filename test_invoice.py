import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import TestCase
from apps.payment.models import Invoice, Payment
from apps.projects.models import Client


class InvoiceTestCase(TestCase):
    def test_invoice_and_payment_client(self):
        payment = Payment.objects.filter(payment_reference="PAY-260001").first()
        invoice = Invoice.objects.filter(invoice_number="INV-260002").first()
        if payment and payment.client:
            print("Payment Client:", payment.client.name, "ID:", payment.client.id)
        if invoice and invoice.client:
            print("Invoice Client:", invoice.client.name, "ID:", invoice.client.id)


