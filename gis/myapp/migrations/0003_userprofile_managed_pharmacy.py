from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0002_storedmediafile'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='managed_pharmacy',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='managed_staff_profiles',
                to='myapp.pharmacy',
                verbose_name='Chi nhanh lam viec',
            ),
        ),
    ]
