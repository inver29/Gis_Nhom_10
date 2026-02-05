from django.contrib import admin
from .models import Pharmacy, Medicine


class MedicineInline(admin.TabularInline):
    model = Medicine
    extra = 1
    fields = ('name', 'price', 'quantity')


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'phone', 'opening_hours', 'has_stock')
    list_filter = ('has_stock',)
    search_fields = ('name', 'address')
    inlines = [MedicineInline]
