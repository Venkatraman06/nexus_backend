from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0002_alter_contract_created_by_alter_contract_updated_by_and_more"),
    ]

    operations = [
        # Drop contract FK from milestone
        migrations.RemoveField(model_name="milestone", name="contract"),
        # Drop contract FK and purchase_order FK from invoice
        migrations.RemoveField(model_name="invoice", name="contract"),
        migrations.RemoveField(model_name="invoice", name="purchase_order"),
        # Drop CustomerPO table (no FKs pointing to it now)
        migrations.DeleteModel(name="CustomerPO"),
        # Drop Contract table
        migrations.DeleteModel(name="Contract"),
    ]
