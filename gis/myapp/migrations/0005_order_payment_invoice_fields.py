from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0004_medicinereview_pharmacyreview'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='invoice_code',
            field=models.CharField(blank=True, db_index=True, default='', max_length=40, verbose_name='Ma hoa don'),
        ),
        migrations.AddField(
            model_name='order',
            name='invoice_requested',
            field=models.BooleanField(default=False, verbose_name='Khach yeu cau xuat hoa don'),
        ),
        migrations.AddField(
            model_name='order',
            name='invoice_staff_name',
            field=models.CharField(blank=True, default='', max_length=150, verbose_name='Nhan vien lap hoa don'),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_method',
            field=models.CharField(choices=[('cod', 'Thanh toan khi nhan hang (COD)'), ('momo', 'Vi MoMo'), ('bank', 'Chuyen khoan ngan hang')], default='cod', max_length=20, verbose_name='Phuong thuc thanh toan'),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_reference',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Ma tham chieu thanh toan'),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(choices=[('cod_waiting', 'Thu tien khi giao hang'), ('awaiting_transfer', 'Cho xac nhan thanh toan'), ('paid', 'Da thanh toan')], default='cod_waiting', max_length=30, verbose_name='Trang thai thanh toan'),
        ),
    ]
