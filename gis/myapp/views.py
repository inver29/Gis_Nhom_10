from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
# [THÊM] Import Q để hỗ trợ tìm kiếm tốt hơn nếu cần sau này
from django.db.models import Q 

from .models import Pharmacy, Medicine, Order, OrderItem, Cart, CartItem
from .forms import CheckoutForm, RegisterForm, LoginForm
from .tool import RoutingTool, calc_shipping_fee

# --- HELPER ---
def get_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart

# --- [SỬA LẠI] VIEWS CHÍNH: HOME CÓ TÌM KIẾM ---
def home(request):
    # Lấy từ khóa tìm kiếm từ URL
    query = request.GET.get('q', '')
    
    if query:
        # Tìm thuốc theo tên (không phân biệt hoa thường)
        medicines = Medicine.objects.filter(name__icontains=query).order_by('-id')
    else:
        # Nếu không tìm, hiện tất cả thuốc mới nhất (hoặc giới hạn 12 cái)
        medicines = Medicine.objects.all().order_by('-id')

    return render(request, 'home.html', {
        'medicines': medicines,
        'query': query
    })

def product_list(request):
    medicines = Medicine.objects.all()
    return render(request, 'products.html', {'medicines': medicines})

def pharmacy_detail(request, pharmacy_id):
    pharmacy = get_object_or_404(Pharmacy, pk=pharmacy_id)
    medicines = Medicine.objects.filter(pharmacy=pharmacy)
    return render(request, 'pharmacy_detail.html', {'pharmacy': pharmacy, 'medicines': medicines})

# --- [SỬA LẠI] GIỎ HÀNG: THÊM XONG KHÔNG CHUYỂN TRANG ---
def add_to_cart(request, medicine_id):
    medicine = get_object_or_404(Medicine, id=medicine_id)
    cart = get_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, medicine=medicine)
    if not created:
        cart_item.quantity += 1
    cart_item.save()
    
    # Hiện thông báo nổi màu xanh
    messages.success(request, f"Đã thêm '{medicine.name}' vào giỏ hàng!")
    
    # Quay lại trang người dùng vừa đứng (Trang chủ hoặc Chi tiết)
    return redirect(request.META.get('HTTP_REFERER', 'home'))

def cart_detail(request):
    cart = get_cart(request)
    return render(request, 'cart.html', {'cart': cart})

def remove_from_cart(request, item_id):
    cart = get_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    return redirect('cart_detail')

# --- CHECKOUT (GIỮ NGUYÊN CODE ĐÃ FIX LỖI TRƯỚC ĐÓ) ---
def checkout(request):
    cart = get_cart(request)
    if not cart.items.exists():
        return redirect('product_list')

    # [FIX LỖI JSON] Chuyển QuerySet thành List Dictionary
    pharmacies_qs = Pharmacy.objects.filter(has_stock=True)
    pharmacies_list = []
    for p in pharmacies_qs:
        pharmacies_list.append({
            'id': p.id,
            'name': p.name,
            'lat': p.lat,
            'lng': p.lng
        })

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Lấy dữ liệu tọa độ từ Map (ẩn)
            lat = request.POST.get('delivery_lat')
            lng = request.POST.get('delivery_lng')
            ship_fee = int(request.POST.get('shipping_fee_value', 0))
            dist = float(request.POST.get('distance_value', 0))
            pharmacy_id = request.POST.get('pharmacy_id')
            
            # --- XỬ LÝ 2 OPTION ---
            has_map_data = lat and lng and pharmacy_id
            has_address_text = form.cleaned_data.get('address_text')

            # Bắt buộc phải có 1 trong 2: Map hoặc Địa chỉ nhập tay
            if not has_map_data and not has_address_text:
                messages.error(request, "Vui lòng nhập địa chỉ cụ thể HOẶC chọn vị trí trên bản đồ!")
                return render(request, 'checkout.html', {
                    'form': form, 'cart': cart, 'pharmacies': pharmacies_list
                })

            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            
            # Nếu dùng Map -> Lưu thông tin GIS
            if has_map_data:
                order.delivery_lat = lat
                order.delivery_lng = lng
                order.distance_km = dist
                order.shipping_fee = ship_fee
                if pharmacy_id:
                    order.pharmacy = Pharmacy.objects.get(id=pharmacy_id)
            else:
                # Nếu chỉ nhập tay -> Phí ship mặc định (ví dụ 30k)
                order.shipping_fee = 30000 
                # Gán tạm vào nhà thuốc đầu tiên
                if pharmacies_qs.exists():
                    order.pharmacy = pharmacies_qs.first()

            order.total_product_price = cart.total_price
            order.final_total_price = cart.total_price + order.shipping_fee
            order.save()

            # Lưu chi tiết đơn hàng
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    medicine=item.medicine,
                    medicine_name=item.medicine.name,
                    price=item.medicine.price,
                    quantity=item.quantity
                )
                item.medicine.quantity -= item.quantity
                item.medicine.save()
            
            cart.items.all().delete()
            messages.success(request, "Đặt hàng thành công!")
            return redirect('order_history')
    else:
        form = CheckoutForm()

    return render(request, 'checkout.html', {
        'form': form, 
        'cart': cart,
        'pharmacies': pharmacies_list 
    })

# --- AUTH ---
def register_view(request):
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
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, "Tên đăng nhập hoặc mật khẩu không đúng")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required(login_url='/login/')
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})

# --- API ---
def get_route_api(request):
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')
    mode = request.GET.get('mode', 'motorbike') 
    dept_time = request.GET.get('dept_time', None)

    if not all([start_lat, start_lng, end_lat, end_lng]):
        return JsonResponse({'error': 'Thiếu tọa độ'}, status=400)

    try:
        tool = RoutingTool()
        result = tool.get_route(start_lat, start_lng, end_lat, end_lng, mode=mode, departure_time_str=dept_time)
        if 'routes' in result:
            for route in result['routes']:
                dist = route.get('distance_km', 0)
                fee_value, fee_text = calc_shipping_fee(dist, mode)
                route['shipping_fee'] = fee_text
                route['shipping_fee_value'] = fee_value
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# [QUAN TRỌNG] Hàm map_view
def map_view(request):
    pharmacies_db = Pharmacy.objects.filter(has_stock=True)
    pharmacy_list = []
    for p in pharmacies_db:
        img_url = p.image.url if p.image else 'https://cdn-icons-png.flaticon.com/512/169/169869.png'
        pharmacy_list.append({
            'id': p.id,
            'name': p.name,
            'address': p.address,
            'phone': p.phone,
            'hours': p.opening_hours,
            'desc': p.desc,
            'image': img_url,
            'lat': p.lat,
            'lng': p.lng
        })
    return render(request, 'map.html', {'pharmacies': pharmacy_list})