from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0011_order_customer_tier_discount'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='cartitem',
            options={
                'verbose_name': 'San pham trong gio',
                'verbose_name_plural': 'San pham trong gio',
                'ordering': ['id'],
            },
        ),
    ]
