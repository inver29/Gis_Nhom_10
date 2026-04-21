from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0003_userprofile_managed_pharmacy'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PharmacyReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='So sao')),
                ('comment', models.TextField(blank=True, verbose_name='Cam nhan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='myapp.pharmacy')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pharmacy_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Danh gia chi nhanh', 'verbose_name_plural': 'Danh gia chi nhanh', 'ordering': ['-updated_at', '-id']},
        ),
        migrations.CreateModel(
            name='MedicineReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='So sao')),
                ('comment', models.TextField(blank=True, verbose_name='Cam nhan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('medicine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='myapp.medicine')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medicine_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Danh gia san pham', 'verbose_name_plural': 'Danh gia san pham', 'ordering': ['-updated_at', '-id']},
        ),
        migrations.AddConstraint(model_name='pharmacyreview', constraint=models.UniqueConstraint(fields=('user', 'pharmacy'), name='unique_user_pharmacy_review')),
        migrations.AddConstraint(model_name='medicinereview', constraint=models.UniqueConstraint(fields=('user', 'medicine'), name='unique_user_medicine_review')),
    ]
