from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0005_order_payment_invoice_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='auto_completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Tu dong hoan thanh'),
        ),
        migrations.AddField(
            model_name='order',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Thoi gian huy'),
        ),
        migrations.AddField(
            model_name='order',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Thoi gian hoan thanh'),
        ),
        migrations.AddField(
            model_name='order',
            name='estimated_delivery_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Thoi gian giao du kien'),
        ),
        migrations.AddField(
            model_name='order',
            name='received_confirmed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Khach xac nhan da nhan'),
        ),
        migrations.CreateModel(
            name='ReturnRefundRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(verbose_name='Ly do tra hang / hoan tien')),
                ('bank_account_number', models.CharField(blank=True, default='', max_length=80, verbose_name='So tai khoan ngan hang')),
                ('momo_account_number', models.CharField(blank=True, default='', max_length=80, verbose_name='So tai khoan MoMo')),
                ('contact_email', models.EmailField(blank=True, default='', max_length=254, verbose_name='Email lien he')),
                ('contact_phone', models.CharField(blank=True, default='', max_length=20, verbose_name='So dien thoai lien he')),
                ('bill_image', models.ImageField(blank=True, null=True, upload_to='returns/bills/', verbose_name='Anh bill / hoa don')),
                ('status', models.CharField(choices=[('processing', 'Dang xu ly'), ('resolved', 'Da xu ly xong')], default='processing', max_length=20, verbose_name='Trang thai xu ly')),
                ('admin_note', models.TextField(blank=True, default='', verbose_name='Ghi chu xu ly noi bo')),
                ('processed_at', models.DateTimeField(blank=True, null=True, verbose_name='Thoi gian xu ly')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='return_request', to='myapp.order')),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_return_requests', to=settings.AUTH_USER_MODEL, verbose_name='Nhan vien xu ly')),
            ],
            options={
                'verbose_name': 'Yeu cau tra hang / hoan tien',
                'verbose_name_plural': 'Yeu cau tra hang / hoan tien',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ReturnRefundEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='returns/evidences/', verbose_name='Anh chung minh')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evidences', to='myapp.returnrefundrequest')),
            ],
            options={
                'verbose_name': 'Anh chung minh tra hang',
                'verbose_name_plural': 'Anh chung minh tra hang',
                'ordering': ['id'],
            },
        ),
    ]
