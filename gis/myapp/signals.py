from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import Order


@receiver(pre_save, sender=Order)
def sync_inventory_when_order_status_changes(sender, instance, **kwargs):
    if not instance.pk:
        return

    previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )
    if previous_status is None or previous_status == instance.status:
        return

    from .views import sync_inventory_for_order_status_transition

    sync_inventory_for_order_status_transition(
        order=instance,
        previous_status=previous_status,
        next_status=instance.status,
    )