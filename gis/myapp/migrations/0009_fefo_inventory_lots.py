from datetime import date

from django.db import migrations, models
import django.db.models.deletion


def seed_inventory_lots(apps, schema_editor):
    Medicine = apps.get_model('myapp', 'Medicine')
    PurchaseImportItem = apps.get_model('myapp', 'PurchaseImportItem')
    MedicineLot = apps.get_model('myapp', 'MedicineLot')
    db_alias = schema_editor.connection.alias

    if MedicineLot.objects.using(db_alias).exists():
        return

    medicines = {medicine.id: medicine for medicine in Medicine.objects.using(db_alias).all()}
    items_by_medicine = {}
    purchase_items = list(
        PurchaseImportItem.objects.using(db_alias)
        .select_related('batch', 'medicine')
        .order_by('medicine_id', 'id')
    )
    for item in purchase_items:
        if not item.medicine_id:
            continue
        items_by_medicine.setdefault(item.medicine_id, []).append(item)

    def build_batch_label(batch):
        if not batch:
            return ''
        if batch.invoice_code:
            return batch.invoice_code
        if batch.pk and batch.created_at:
            return f"NHAP{batch.created_at.strftime('%Y%m%d')}-{batch.pk:05d}"
        return f"NHAP-{batch.pk or 'TAM'}"

    def item_sort_key_desc(item):
        expiry_value = item.expiry_date or date.max
        created_value = item.batch.created_at if getattr(item, 'batch', None) and item.batch.created_at else date.min
        return (expiry_value, created_value, item.id)

    processed_ids = set()
    for medicine_id, items in items_by_medicine.items():
        medicine = medicines.get(medicine_id)
        if medicine is None:
            continue
        processed_ids.add(medicine_id)
        remaining_target = max(int(medicine.quantity or 0), 0)

        for item in sorted(items, key=item_sort_key_desc, reverse=True):
            imported_quantity = max(int(item.imported_quantity or 0), 0)
            if imported_quantity <= 0:
                continue

            remaining_quantity = min(imported_quantity, remaining_target)
            remaining_target -= remaining_quantity

            MedicineLot.objects.using(db_alias).create(
                medicine_id=medicine.id,
                pharmacy_id=medicine.pharmacy_id,
                purchase_batch_id=item.batch_id,
                purchase_item_id=item.id,
                source_type='purchase_import',
                source_label=build_batch_label(getattr(item, 'batch', None)),
                import_price=max(int(item.import_price or 0), 0),
                expiry_date=item.expiry_date,
                received_quantity=imported_quantity,
                remaining_quantity=remaining_quantity,
                note=item.note or '',
            )

        if remaining_target > 0:
            MedicineLot.objects.using(db_alias).create(
                medicine_id=medicine.id,
                pharmacy_id=medicine.pharmacy_id,
                source_type='manual_adjustment',
                source_label='Tồn kho mở đầu',
                import_price=0,
                expiry_date=medicine.expiry_date,
                received_quantity=remaining_target,
                remaining_quantity=remaining_target,
                note='Dữ liệu tồn kho có sẵn trước khi kích hoạt FEFO.',
            )

    for medicine in medicines.values():
        if medicine.id in processed_ids:
            continue
        opening_quantity = max(int(medicine.quantity or 0), 0)
        if opening_quantity <= 0:
            continue
        MedicineLot.objects.using(db_alias).create(
            medicine_id=medicine.id,
            pharmacy_id=medicine.pharmacy_id,
            source_type='manual_adjustment',
            source_label='Tồn kho mở đầu',
            import_price=0,
            expiry_date=medicine.expiry_date,
            received_quantity=opening_quantity,
            remaining_quantity=opening_quantity,
            note='Dữ liệu tồn kho có sẵn trước khi kích hoạt FEFO.',
        )

    today = date.today()
    for medicine in Medicine.objects.using(db_alias).all():
        remaining_qs = MedicineLot.objects.using(db_alias).filter(medicine_id=medicine.id, remaining_quantity__gt=0)
        sellable_total = (
            remaining_qs.filter(models.Q(expiry_date__isnull=True) | models.Q(expiry_date__gte=today))
            .aggregate(total=models.Sum('remaining_quantity'))
            .get('total')
            or 0
        )
        next_expiry = remaining_qs.exclude(expiry_date__isnull=True).order_by('expiry_date', 'id').values_list('expiry_date', flat=True).first()
        Medicine.objects.using(db_alias).filter(pk=medicine.id).update(quantity=sellable_total, expiry_date=next_expiry)


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0008_medicine_expiry_purchase_import_and_return_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicineLot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_type', models.CharField(choices=[('purchase_import', 'Nhập hàng'), ('manual_adjustment', 'Điều chỉnh tay'), ('return_restore', 'Hoàn kho từ đơn hàng')], default='purchase_import', max_length=30, verbose_name='Nguồn tạo lô')),
                ('source_label', models.CharField(blank=True, default='', max_length=120, verbose_name='Nhãn nguồn')),
                ('import_price', models.PositiveIntegerField(default=0, verbose_name='Giá nhập')),
                ('expiry_date', models.DateField(blank=True, null=True, verbose_name='Hạn sử dụng')),
                ('received_quantity', models.PositiveIntegerField(default=0, verbose_name='Số lượng nhập lô')),
                ('remaining_quantity', models.PositiveIntegerField(default=0, verbose_name='Số lượng còn lại')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Ghi chú')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('medicine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots', to='myapp.medicine', verbose_name='Thuốc')),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medicine_lots', to='myapp.pharmacy', verbose_name='Chi nhánh')),
                ('purchase_batch', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medicine_lots', to='myapp.purchaseimportbatch', verbose_name='Phiếu nhập nguồn')),
                ('purchase_item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medicine_lots', to='myapp.purchaseimportitem', verbose_name='Dòng nhập nguồn')),
            ],
            options={
                'verbose_name': 'Lô tồn kho thuốc',
                'verbose_name_plural': 'Lô tồn kho thuốc',
                'ordering': ['expiry_date', 'created_at', 'id'],
            },
        ),
        migrations.CreateModel(
            name='OrderItemLotAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=0, verbose_name='Số lượng phân bổ')),
                ('lot_expiry_date', models.DateField(blank=True, null=True, verbose_name='HSD snapshot')),
                ('lot_import_price', models.PositiveIntegerField(default=0, verbose_name='Giá nhập snapshot')),
                ('lot_source_label', models.CharField(blank=True, default='', max_length=120, verbose_name='Nhãn lô snapshot')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_allocations', to='myapp.medicinelot', verbose_name='Lô thuốc')),
                ('order_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lot_allocations', to='myapp.orderitem', verbose_name='Dòng đơn hàng')),
            ],
            options={
                'verbose_name': 'Phân bổ lô cho dòng đơn',
                'verbose_name_plural': 'Phân bổ lô cho dòng đơn',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='medicinelot',
            index=models.Index(fields=['medicine', 'expiry_date'], name='idx_medlot_med_exp'),
        ),
        migrations.AddIndex(
            model_name='medicinelot',
            index=models.Index(fields=['pharmacy', 'expiry_date'], name='idx_medlot_pharm_exp'),
        ),
        migrations.RunPython(seed_inventory_lots, migrations.RunPython.noop),
    ]
