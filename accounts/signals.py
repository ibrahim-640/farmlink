# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Order, Notification

# ---------------------------
# AUTO CREATE PROFILE
# When a new User is created,
# automatically create their Profile
# ---------------------------
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """
    Fires when a User object is saved.
    'created' is True only when it is a brand new user.
    We create a Profile linked to that user automatically.
    """
    if created:
        Profile.objects.create(
            user=instance,
            role=Profile.ROLE_BUYER  # default role, views update this
        )


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    """
    Fires every time a User is saved.
    We also save the related Profile to keep them in sync.
    """
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        pass


# ---------------------------
# AUTO NOTIFY FARMER
# When a new Order is created,
# automatically send notification
# to the farmer whose product was ordered
# ---------------------------
@receiver(post_save, sender=Order)
def notify_farmer_on_new_order(sender, instance, created, **kwargs):
    """
    Fires when an Order is saved.
    'created' is True only for brand new orders.

    When a buyer places an order:
    1. We find which farmer owns the product
    2. We create a Notification for that farmer
    3. Farmer sees it on their notifications page
    """
    if created:
        farmer = instance.product.farmer

        Notification.objects.create(
            user=farmer,
            message=(
                f"New order received! "
                f"{instance.buyer.username} ordered "
                f"{instance.quantity} {instance.product.unit} "
                f"of {instance.product.name} "
                f"worth KSh {instance.total_price}."
            ),
            notification_type='order'
        )


# ---------------------------
# AUTO NOTIFY BUYER
# When an order STATUS changes,
# notify the buyer about the update
# ---------------------------
@receiver(post_save, sender=Order)
def notify_buyer_on_order_update(sender, instance, created, **kwargs):
    """
    Fires every time an Order is saved.
    We skip newly created orders (created=True)
    because that is handled above.

    When order status changes we notify the buyer:
    - confirmed → "Your order has been confirmed"
    - in_transit → "Your order is on the way"
    - delivered → "Your order has been delivered"
    - cancelled → "Your order was cancelled"
    """
    if not created:
        # Map each status to a human readable message
        status_messages = {
            'confirmed': (
                f"Your order #{instance.id} for "
                f"{instance.product.name} has been confirmed."
            ),
            'in_transit': (
                f"Your order #{instance.id} for "
                f"{instance.product.name} is now in transit."
            ),
            'delivered': (
                f"Your order #{instance.id} for "
                f"{instance.product.name} has been delivered. "
                f"Thank you!"
            ),
            'cancelled': (
                f"Your order #{instance.id} for "
                f"{instance.product.name} was cancelled."
            ),
        }

        message = status_messages.get(instance.status)

        # Only create notification if status has a message
        if message:
            Notification.objects.create(
                user=instance.buyer,
                message=message,
                notification_type='order'
            )