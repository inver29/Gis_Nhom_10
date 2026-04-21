from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MaxValueValidator, MinValueValidator


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0009_fefo_inventory_lots'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicinePromotion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, default='', max_length=150, verbose_name='Tên chương trình')),
                ('discount_percent', models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(95)], verbose_name='Phần trăm giảm')),
                ('start_date', models.DateField(blank=True, null=True, verbose_name='Ngày bắt đầu')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='Ngày kết thúc')),
                ('is_active', models.BooleanField(default=True, verbose_name='Đang áp dụng')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Ghi chú')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medicine_promotions', to='auth.user', verbose_name='Người tạo')),
                ('medicine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='promotions', to='myapp.medicine', verbose_name='Sản phẩm áp dụng')),
            ],
            options={
                'verbose_name': 'Khuyến mãi sản phẩm',
                'verbose_name_plural': 'Khuyến mãi sản phẩm',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='medicinepromotion',
            index=models.Index(fields=['is_active', 'start_date', 'end_date'], name='idx_medpromo_active'),
        ),
    ]
