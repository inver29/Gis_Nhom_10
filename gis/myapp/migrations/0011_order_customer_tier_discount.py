from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0010_medicine_promotion'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='customer_tier_discount_percent',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Muc giam theo hang KH (%)'),
        ),
        migrations.AddField(
            model_name='order',
            name='customer_tier_discount_total',
            field=models.PositiveIntegerField(default=0, verbose_name='Tong tien giam theo hang KH'),
        ),
        migrations.AddField(
            model_name='order',
            name='customer_tier_name',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='Hang khach hang luc dat'),
        ),
    ]
