from django.db import migrations, models
from django.utils.text import slugify


def populate_slug(apps, schema_editor):
    LeaveType = apps.get_model('attendance', 'LeaveType')
    for lt in LeaveType.objects.all():
        lt.slug = slugify(lt.name)
        lt.save(update_fields=['slug'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0009_shiftchangerequest_wfhrequest'),
    ]

    operations = [
        migrations.RemoveField(model_name='leavetype', name='created_by'),
        migrations.RemoveField(model_name='leavetype', name='updated_by'),
        migrations.RemoveField(model_name='leavetype', name='is_deleted'),
        migrations.AlterField(
            model_name='leavetype',
            name='name',
            field=models.CharField(max_length=200, unique=True),
        ),
        migrations.AddField(
            model_name='leavetype',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=200, db_index=False),
        ),
        migrations.RunPython(populate_slug, noop),
        migrations.AlterField(
            model_name='leavetype',
            name='slug',
            field=models.SlugField(blank=True, max_length=200, unique=True),
        ),
    ]
