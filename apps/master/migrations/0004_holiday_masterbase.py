from django.db import migrations, models
from django.utils.text import slugify


def populate_slug(apps, schema_editor):
    Holiday = apps.get_model('master', 'Holiday')
    for h in Holiday.objects.all():
        base = slugify(h.name)
        h.slug = f"{base}-{h.date.isoformat()}" if h.date else base
        h.save(update_fields=['slug'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0003_leavetype'),
    ]

    operations = [
        migrations.AddField(
            model_name='holiday',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=200, db_index=False),
        ),
        migrations.RunPython(populate_slug, noop),
        migrations.AlterField(
            model_name='holiday',
            name='slug',
            field=models.SlugField(blank=True, max_length=200, unique=True),
        ),
        migrations.AlterModelOptions(
            name='holiday',
            options={'ordering': ['date'], 'verbose_name': 'holiday', 'verbose_name_plural': 'holidays'},
        ),
    ]
