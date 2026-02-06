from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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

# --- VIEWS CHÍNH ---
def home(request):
    query = request.GET.get('q', '')
    if query:
        medicines = Medicine.objects.filter(name__icontains=query).order_by('-id')
    else:
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

# --- GIỎ HÀNG ---
def add_to_cart(request, medicine_id):
    medicine = get_object_or_404(Medicine, id=medicine_id)
    cart = get_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, medicine=medicine)
    if not created:
        cart_item.quantity += 1
    cart_item.save()
    
    messages.success(request, f"Đã thêm '{medicine.name}' vào giỏ hàng!")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

def cart_detail(request):
    cart = get_cart(request)
    return render(request, 'cart.html', {'cart': cart})

def remove_from_cart(request, item_id):
    cart = get_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    return redirect('cart_detail')

# --- CHECKOUT (ĐÃ SỬA LỖI & LOGIC) ---
def checkout(request):
    cart = get_cart(request)
    if not cart.items.exists():
        return redirect('product_list')

    # 1. Kiểm tra tồn kho trước khi cho đặt
    for item in cart.items.all():
        if item.quantity > item.medicine.quantity:
            messages.error(request, f"Xin lỗi, thuốc '{item.medicine.name}' chỉ còn {item.medicine.quantity} sản phẩm!")
            return redirect('cart_detail')

    # 2. Chuẩn bị dữ liệu Map
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
            # --- LẤY DỮ LIỆU TỪ FORM ---
            # Dùng .strip() để loại bỏ khoảng trắng thừa nếu có
            lat = request.POST.get('delivery_lat', '').strip()
            lng = request.POST.get('delivery_lng', '').strip()
            pharmacy_id = request.POST.get('pharmacy_id', '').strip()
            
            # Lấy địa chỉ nhập tay
            address_text = form.cleaned_data.get('address_text', '')
            if address_text:
                address_text = address_text.strip()

            # --- KIỂM TRA ĐIỀU KIỆN CHẶT CHẼ ---
            has_map_data = bool(lat and lng and pharmacy_id)
            has_address_text = bool(address_text)

            # NẾU CẢ 2 ĐỀU THIẾU -> BÁO LỖI VÀ CHẶN LUÔN
            if not has_map_data and not has_address_text:
                messages.error(request, "⚠️ Vui lòng nhập địa chỉ cụ thể HOẶC chọn vị trí trên bản đồ để tính phí ship!")
                return render(request, 'checkout.html', {'form': form, 'cart': cart, 'pharmacies': pharmacies_list})

            # --- XỬ LÝ SỐ LIỆU AN TOÀN (TRY/EXCEPT) ---
            # Khắc phục lỗi ValueError: invalid literal for int() with base 10: ''
            ship_fee_raw = request.POST.get('shipping_fee_value', '')
            try:
                # Nếu chuỗi rỗng thì gán = 0
                ship_fee = int(ship_fee_raw) if ship_fee_raw else 0
            except ValueError:
                ship_fee = 0

            dist_raw = request.POST.get('distance_value', '')
            try:
                dist = float(dist_raw) if dist_raw else 0.0
            except ValueError:
                dist = 0.0

            # --- LƯU ĐƠN HÀNG ---
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            
            # Nếu có Map -> Lưu theo Map
            if has_map_data:
                try:
                    order.delivery_lat = float(lat)
                    order.delivery_lng = float(lng)
                    order.distance_km = dist
                    order.shipping_fee = ship_fee
                    if pharmacy_id:
                        order.pharmacy = Pharmacy.objects.get(id=pharmacy_id)
                except (ValueError, Pharmacy.DoesNotExist):
                    pass # Bỏ qua nếu dữ liệu hack/lỗi
            
            # Nếu chỉ có nhập tay -> Lưu mặc định
            else:
                order.shipping_fee = 30000 # Phí ship mặc định
                if pharmacies_qs.exists():
                    order.pharmacy = pharmacies_qs.first() # Gán tạm vào chi nhánh đầu tiên

            order.total_product_price = cart.total_price
            order.final_total_price = cart.total_price + order.shipping_fee
            order.save()

            # --- LƯU CHI TIẾT & TRỪ KHO ---
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    medicine=item.medicine,
                    medicine_name=item.medicine.name,
                    price=item.medicine.price,
                    quantity=item.quantity
                )
                # Trừ kho
                item.medicine.quantity = item.medicine.quantity - item.quantity
                if item.medicine.quantity < 0: item.medicine.quantity = 0
                item.medicine.save()
            
            cart.items.all().delete()
            messages.success(request, "Đặt hàng thành công!")
            return redirect('order_history')
        else:
            messages.error(request, "Thông tin chưa hợp lệ. Vui lòng kiểm tra lại họ tên và số điện thoại.")
            
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