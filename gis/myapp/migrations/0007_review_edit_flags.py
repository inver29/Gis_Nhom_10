from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0006_order_fulfillment_and_return_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicinereview',
            name='is_edited',
            field=models.BooleanField(default=False, verbose_name='Da cap nhat lai'),
        ),
        migrations.AddField(
            model_name='pharmacyreview',
            name='is_edited',
            field=models.BooleanField(default=False, verbose_name='Da cap nhat lai'),
        ),
    ]
