from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CheckoutForm, LoginForm, RegisterForm
from .models import Cart, CartItem, Medicine, Order, OrderItem, Pharmacy
from .tool import DeliveryRoutingService


delivery_service = DeliveryRoutingService()


def get_or_create_cart(request):
    """
    Lấy giỏ hàng hiện tại của người dùng.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart


def get_available_pharmacies():
    """
    Lấy danh sách nhà thuốc còn ít nhất một loại thuốc có tồn kho.
    """
    return Pharmacy.objects.filter(medicines__quantity__gt=0).distinct()


def build_checkout_pharmacy_payload(pharmacy_queryset):
    """
    Chuẩn bị dữ liệu nhà thuốc cho trang checkout.
    """
    return [
        {
            'id': pharmacy.id,
            'name': pharmacy.name,
            'lat': pharmacy.lat,
            'lng': pharmacy.lng,
        }
        for pharmacy in pharmacy_queryset
    ]


def build_map_pharmacy_payload(pharmacy_queryset):
    """
    Chuẩn bị dữ liệu nhà thuốc cho trang bản đồ.
    """
    pharmacy_payload = []

    for pharmacy in pharmacy_queryset:
        image_url = (
            pharmacy.image.url
            if pharmacy.image
            else 'https://cdn-icons-png.flaticon.com/512/169/169869.png'
        )

        pharmacy_payload.append(
            {
                'id': pharmacy.id,
                'name': pharmacy.name,
                'address': pharmacy.address,
                'phone': pharmacy.phone,
                'hours': pharmacy.opening_hours,
                'desc': pharmacy.desc,
                'image': image_url,
                'lat': pharmacy.lat,
                'lng': pharmacy.lng,
            }
        )

    return pharmacy_payload


def verify_cart_stock(cart):
    """
    Kiểm tra toàn bộ sản phẩm trong giỏ có đủ tồn kho hay không.
    """
    for cart_item in cart.items.select_related('medicine').all():
        if cart_item.quantity > cart_item.medicine.quantity:
            return (
                False,
                f"Xin lỗi, thuốc '{cart_item.medicine.name}' chỉ còn {cart_item.medicine.quantity} sản phẩm.",
            )

    return True, ''


def home(request):
    """
    Trang chủ hiển thị danh sách thuốc và hỗ trợ tìm kiếm.
    """
    search_keyword = request.GET.get('q', '').strip()
    medicine_queryset = Medicine.objects.select_related('pharmacy').all()

    if search_keyword:
        medicine_queryset = medicine_queryset.filter(
            Q(name__icontains=search_keyword)
            | Q(description__icontains=search_keyword)
            | Q(pharmacy__name__icontains=search_keyword)
        )

    medicines = medicine_queryset.order_by('-id')
    return render(request, 'home.html', {'medicines': medicines, 'query': search_keyword})


def product_list(request):
    """
    Trang danh sách toàn bộ sản phẩm.
    """
    medicines = Medicine.objects.select_related('pharmacy').all().order_by('-id')
    return render(request, 'products.html', {'medicines': medicines})


def pharmacy_detail(request, pharmacy_id):
    """
    Trang chi tiết một nhà thuốc.
    """
    pharmacy = get_object_or_404(Pharmacy, pk=pharmacy_id)
    medicines = Medicine.objects.filter(pharmacy=pharmacy).order_by('name')
    return render(request, 'pharmacy_detail.html', {'pharmacy': pharmacy, 'medicines': medicines})


def add_to_cart(request, medicine_id):
    """
    Thêm 1 sản phẩm vào giỏ hàng.
    """
    medicine = get_object_or_404(Medicine, id=medicine_id)
    cart = get_or_create_cart(request)

    if medicine.quantity <= 0:
        messages.error(request, f"Thuốc '{medicine.name}' hiện đã hết hàng.")
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    cart_item, created = CartItem.objects.get_or_create(cart=cart, medicine=medicine)

    if created:
        cart_item.quantity = 1
    elif cart_item.quantity < medicine.quantity:
        cart_item.quantity += 1
    else:
        messages.error(request, f"Thuốc '{medicine.name}' không đủ tồn kho để thêm tiếp.")
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    cart_item.save()
    messages.success(request, f"Đã thêm '{medicine.name}' vào giỏ hàng.")
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def cart_detail(request):
    """
    Trang xem giỏ hàng.
    """
    cart = get_or_create_cart(request)
    return render(request, 'cart.html', {'cart': cart})


def remove_from_cart(request, item_id):
    """
    Xóa một sản phẩm khỏi giỏ hàng.
    """
    cart = get_or_create_cart(request)
    cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
    cart_item.delete()
    return redirect('cart_detail')


def checkout(request):
    """
    Xử lý trang thanh toán.
    """
    cart = get_or_create_cart(request)

    if not cart.items.exists():
        return redirect('product_list')

    stock_is_valid, stock_error_message = verify_cart_stock(cart)
    if not stock_is_valid:
        messages.error(request, stock_error_message)
        return redirect('cart_detail')

    available_pharmacies = get_available_pharmacies()
    pharmacy_payload = build_checkout_pharmacy_payload(available_pharmacies)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if not form.is_valid():
            messages.error(request, 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại biểu mẫu.')
            return render(request, 'checkout.html', {'form': form, 'cart': cart, 'pharmacies': pharmacy_payload})

        delivery_lat = request.POST.get('delivery_lat', '').strip()
        delivery_lng = request.POST.get('delivery_lng', '').strip()
        selected_pharmacy_id = request.POST.get('pharmacy_id', '').strip()

        if not delivery_lat or not delivery_lng:
            messages.error(request, 'Vui lòng chọn vị trí giao hàng trên bản đồ để hệ thống tính chi nhánh và phí ship.')
            return render(request, 'checkout.html', {'form': form, 'cart': cart, 'pharmacies': pharmacy_payload})

        best_delivery_result = None

        if selected_pharmacy_id:
            selected_pharmacy = available_pharmacies.filter(id=selected_pharmacy_id).first()

            if selected_pharmacy:
                route_result = delivery_service.estimate_route(
                    start_lat=selected_pharmacy.lat,
                    start_lng=selected_pharmacy.lng,
                    end_lat=delivery_lat,
                    end_lng=delivery_lng,
                    delivery_mode='motorbike',
                )

                if 'routes' in route_result and route_result['routes']:
                    best_delivery_result = {
                        'pharmacy': selected_pharmacy,
                        'route': route_result['routes'][0],
                    }

        if best_delivery_result is None:
            best_delivery_result = delivery_service.choose_best_pharmacy(
                pharmacies=available_pharmacies,
                delivery_lat=delivery_lat,
                delivery_lng=delivery_lng,
                delivery_mode='motorbike',
            )

        if 'error' in best_delivery_result:
            messages.error(request, best_delivery_result['error'])
            return render(request, 'checkout.html', {'form': form, 'cart': cart, 'pharmacies': pharmacy_payload})

        stock_is_valid, stock_error_message = verify_cart_stock(cart)
        if not stock_is_valid:
            messages.error(request, stock_error_message)
            return redirect('cart_detail')

        selected_pharmacy = best_delivery_result['pharmacy']
        selected_route = best_delivery_result['route']

        with transaction.atomic():
            order = form.save(commit=False)

            if request.user.is_authenticated:
                order.user = request.user

            order.delivery_lat = float(delivery_lat)
            order.delivery_lng = float(delivery_lng)
            order.pharmacy = selected_pharmacy
            order.distance_km = selected_route['distance_km']
            order.shipping_fee = selected_route['shipping_fee_value']
            order.total_product_price = cart.total_price
            order.final_total_price = cart.total_price + order.shipping_fee
            order.save()

            for cart_item in cart.items.select_related('medicine').all():
                medicine = cart_item.medicine

                if cart_item.quantity > medicine.quantity:
                    raise ValueError(f"Thuốc '{medicine.name}' không đủ tồn kho để hoàn tất đơn.")

                OrderItem.objects.create(
                    order=order,
                    medicine=medicine,
                    medicine_name=medicine.name,
                    price=medicine.price,
                    quantity=cart_item.quantity,
                )

                medicine.quantity -= cart_item.quantity
                if medicine.quantity < 0:
                    medicine.quantity = 0
                medicine.save()

            cart.items.all().delete()

        messages.success(request, 'Đặt hàng thành công.')
        return redirect('order_history')

    form = CheckoutForm()
    return render(request, 'checkout.html', {'form': form, 'cart': cart, 'pharmacies': pharmacy_payload})


def register_view(request):
    """
    Xử lý đăng ký tài khoản.
    """
    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


def login_view(request):
    """
    Xử lý đăng nhập.
    """
    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect('home')

            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """
    Đăng xuất tài khoản.
    """
    logout(request)
    return redirect('home')


@login_required(login_url='/login/')
def order_history(request):
    """
    Hiển thị lịch sử đơn hàng của người dùng đang đăng nhập.
    """
    orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})


def get_route_api(request):
    """
    API lấy tuyến đường giữa 2 điểm.
    """
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')
    delivery_mode = request.GET.get('mode', 'motorbike')

    if not all([start_lat, start_lng, end_lat, end_lng]):
        return JsonResponse({'error': 'Thiếu tọa độ.'}, status=400)

    route_result = delivery_service.estimate_route(
        start_lat=start_lat,
        start_lng=start_lng,
        end_lat=end_lat,
        end_lng=end_lng,
        delivery_mode=delivery_mode,
    )

    status_code = 200 if 'routes' in route_result else 400
    return JsonResponse(route_result, status=status_code)


def find_best_pharmacy_api(request):
    """
    API tìm chi nhánh phù hợp nhất cho vị trí giao hàng.
    """
    delivery_lat = request.GET.get('delivery_lat')
    delivery_lng = request.GET.get('delivery_lng')
    delivery_mode = request.GET.get('mode', 'motorbike')

    if not all([delivery_lat, delivery_lng]):
        return JsonResponse({'error': 'Thiếu tọa độ giao hàng.'}, status=400)

    available_pharmacies = get_available_pharmacies()

    best_delivery_result = delivery_service.choose_best_pharmacy(
        pharmacies=available_pharmacies,
        delivery_lat=delivery_lat,
        delivery_lng=delivery_lng,
        delivery_mode=delivery_mode,
    )

    if 'error' in best_delivery_result:
        return JsonResponse(best_delivery_result, status=400)

    selected_pharmacy = best_delivery_result['pharmacy']

    response_data = {
        'pharmacy': {
            'id': selected_pharmacy.id,
            'name': selected_pharmacy.name,
            'address': selected_pharmacy.address,
            'phone': selected_pharmacy.phone,
            'lat': selected_pharmacy.lat,
            'lng': selected_pharmacy.lng,
        },
        'route': best_delivery_result['route'],
        'mode': best_delivery_result.get('mode', delivery_mode),
    }

    return JsonResponse(response_data)


def map_view(request):
    """
    Trang bản đồ hiển thị danh sách các nhà thuốc còn hàng.
    """
    pharmacies = get_available_pharmacies()
    pharmacy_payload = build_map_pharmacy_payload(pharmacies)
    return render(request, 'map.html', {'pharmacies': pharmacy_payload})