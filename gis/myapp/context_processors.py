from .models import Cart, UserProfile


def site_chrome(request):
    cart_items_count = 0
    cart = None
    user_profile = None
    user_display_name = ""

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).prefetch_related("items").first()
        user_profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={"full_name": request.user.get_full_name() or request.user.username},
        )
        user_display_name = (
            user_profile.full_name
            or request.user.get_full_name()
            or request.user.first_name
            or request.user.username
        )
    else:
        session_key = request.session.session_key
        if session_key:
            cart = Cart.objects.filter(session_key=session_key).prefetch_related("items").first()

    if cart is not None:
        cart_items_count = sum(item.quantity for item in cart.items.all())

    return {
        "cart_items_count": cart_items_count,
        "user_profile": user_profile,
        "user_display_name": user_display_name,
    }
