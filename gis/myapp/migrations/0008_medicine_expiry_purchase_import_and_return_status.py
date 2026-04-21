from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_review_edit_flags'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='medicine',
            name='expiry_date',
            field=models.DateField(blank=True, null=True, verbose_name='Han su dung'),
        ),
        migrations.AlterField(
            model_name='returnrefundrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('processing', 'Dang xu ly'),
                    ('approved_refund', 'Chap nhan hoan tien'),
                    ('rejected_refund', 'Tu choi hoan tien'),
                ],
                default='processing',
                max_length=20,
                verbose_name='Trang thai xu ly',
            ),
        ),
        migrations.CreateModel(
            name='PurchaseImportBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_code', models.CharField(blank=True, db_index=True, default='', max_length=80, verbose_name='Ma hoa don nhap')),
                ('source_file', models.FileField(upload_to='imports/excel/', verbose_name='File Excel nhap hang')),
                ('imported_by_name', models.CharField(blank=True, default='', max_length=150, verbose_name='Ho ten nguoi phu trach')),
                ('note', models.TextField(blank=True, default='', verbose_name='Ghi chu')),
                ('total_lines', models.PositiveIntegerField(default=0, verbose_name='So dong hop le')),
                ('total_quantity', models.PositiveIntegerField(default=0, verbose_name='Tong so luong nhap')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Thoi gian nhap')),
                ('imported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_import_batches', to=settings.AUTH_USER_MODEL, verbose_name='Nguoi phu trach nhap hang')),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='purchase_import_batches', to='myapp.pharmacy', verbose_name='Chi nhanh nhap hang')),
            ],
            options={
                'verbose_name': 'Phieu nhap hang',
                'verbose_name_plural': 'Nhap hang bang Excel',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='PurchaseImportItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('medicine_name', models.CharField(max_length=200, verbose_name='Ten thuoc')),
                ('manufacturer', models.CharField(blank=True, default='', max_length=150, verbose_name='Nha san xuat')),
                ('unit', models.CharField(blank=True, default='', max_length=50, verbose_name='Don vi tinh')),
                ('previous_quantity', models.PositiveIntegerField(default=0, verbose_name='Ton truoc khi nhap')),
                ('imported_quantity', models.PositiveIntegerField(default=0, verbose_name='So luong nhap')),
                ('new_quantity', models.PositiveIntegerField(default=0, verbose_name='Ton sau khi nhap')),
                ('import_price', models.PositiveIntegerField(default=0, verbose_name='Gia nhap')),
                ('expiry_date', models.DateField(blank=True, null=True, verbose_name='Han su dung nhap vao')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Ghi chu dong')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='myapp.purchaseimportbatch')),
                ('medicine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_import_items', to='myapp.medicine')),
            ],
            options={
                'verbose_name': 'Chi tiet nhap hang',
                'verbose_name_plural': 'Chi tiet nhap hang',
                'ordering': ['id'],
            },
        ),
    ]
