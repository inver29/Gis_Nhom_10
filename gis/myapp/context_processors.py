from .models import Cart, UserProfile


def site_chrome(request):
    cart_items_count = 0
    cart = None
    user_profile = None
    user_display_name = ""

    user = getattr(request, "user", None)
    session = getattr(request, "session", None)

    if getattr(user, "is_authenticated", False):
        cart = Cart.objects.filter(user=user).prefetch_related("items").first()
        user_profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"full_name": user.get_full_name() or user.username},
        )
        user_display_name = (
            user_profile.full_name
            or user.get_full_name()
            or user.first_name
            or user.username
        )
    else:
        session_key = getattr(session, "session_key", None)
        if session_key:
            cart = Cart.objects.filter(session_key=session_key).prefetch_related("items").first()

    if cart is not None:
        cart_items_count = sum(item.quantity for item in cart.items.all())

    admin_permissions = {}
    if getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
        from .views import get_user_admin_permissions  # Lazy import to avoid module cycle during startup.

        admin_permissions = get_user_admin_permissions(user)

    return {
        "cart_items_count": cart_items_count,
        "user_profile": user_profile,
        "user_display_name": user_display_name,
        "admin_permissions": admin_permissions,
    }
