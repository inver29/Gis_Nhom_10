from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import Http404
from django.contrib.auth.decorators import user_passes_test
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.models import User

from .forms import (
    AccountProfileForm,
    CheckoutForm,
    RegisterForm,
    LoginForm,
    PharmacyAdminForm,
    MedicineAdminForm,
    OrderStatusUpdateForm,
    CustomUserCreateForm,
    CustomUserUpdateForm,
)
from .emails import (
    send_order_cancelled_email,
    send_order_confirmation_email,
    send_order_invoice_email,
)
from .models import Cart, CartItem, Medicine, Order, OrderItem, Pharmacy, UserProfile
from .tool import (
    DeliveryRoutingService,
    calculate_air_distance_km,
    estimate_road_distance_km,
    reverse_geocode_coordinates,
    search_address_candidates,
)


delivery_service = DeliveryRoutingService()
PHARMACY_FALLBACK_IMAGE = "/media/pharmacies/pm.jpg"
MEDICINE_FALLBACK_IMAGE = "/media/medicines/oresol.jpg"


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


def get_cart_items_count(cart):
    return sum(item.quantity for item in cart.items.all())


def request_expects_json(request):
    accept_header = request.headers.get('Accept', '')
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in accept_header
    )


def get_safe_redirect_url(request, default='home'):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse(default)


def is_customer_user(user):
    return user.is_authenticated and not user.is_staff and not user.is_superuser


def get_or_create_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'full_name': user.get_full_name() or user.username,
            'phone': '',
            'address_text': '',
        },
    )
    return profile


def get_user_display_name(user):
    if not user.is_authenticated:
        return ''

    profile = get_or_create_user_profile(user)
    return (
        profile.full_name.strip()
        or user.get_full_name().strip()
        or user.first_name.strip()
        or user.username
    )


def get_entity_gallery_urls(instance, fallback_url):
    urls = list(getattr(instance, 'gallery_image_list', []) or [])
    if not urls and fallback_url:
        urls.append(fallback_url)

    return urls


def build_saved_address_payload(profile):
    if not profile or not profile.address_text:
        return None

    return {
        'address_text': profile.address_text,
        'lat': profile.address_lat,
        'lng': profile.address_lng,
    }


def update_profile_from_checkout(user, order):
    if not user.is_authenticated:
        return

    if not is_customer_user(user):
        return

    profile = get_or_create_user_profile(user)
    profile.address_text = order.address_text or ''
    profile.address_lat = order.delivery_lat
    profile.address_lng = order.delivery_lng
    profile.save(update_fields=['address_text', 'address_lat', 'address_lng', 'updated_at'])


def normalize_medicine_key(name, unit, manufacturer='', origin=''):
    return (
        (name or '').strip().casefold(),
        (unit or '').strip().casefold(),
        (manufacturer or '').strip().casefold(),
        (origin or '').strip().casefold(),
    )


def normalize_catalog_key(name, unit, manufacturer=''):
    return (
        (name or '').strip().casefold(),
        (unit or '').strip().casefold(),
        (manufacturer or '').strip().casefold(),
    )


def build_cart_requirements(cart):
    grouped_requirements = {}

    for cart_item in cart.items.select_related('medicine').all():
        key = normalize_medicine_key(
            cart_item.medicine.name,
            cart_item.medicine.unit,
            cart_item.medicine.manufacturer,
            cart_item.medicine.origin,
        )
        if key not in grouped_requirements:
            grouped_requirements[key] = {
                'name': cart_item.medicine.name,
                'unit': cart_item.medicine.unit,
                'manufacturer': cart_item.medicine.manufacturer,
                'origin': cart_item.medicine.origin,
                'quantity': 0,
            }
        grouped_requirements[key]['quantity'] += cart_item.quantity

    return list(grouped_requirements.values())


def allocate_requirements_to_medicines(requirements, medicines):
    medicines_by_key = {}

    for medicine in medicines:
        key = normalize_medicine_key(
            medicine.name,
            medicine.unit,
            medicine.manufacturer,
            medicine.origin,
        )
        medicines_by_key.setdefault(key, medicine)

    allocations = []

    for requirement in requirements:
        key = normalize_medicine_key(
            requirement['name'],
            requirement['unit'],
            requirement.get('manufacturer', ''),
            requirement.get('origin', ''),
        )
        matched_medicine = medicines_by_key.get(key)
        if matched_medicine is None or matched_medicine.quantity < requirement['quantity']:
            return None

        allocations.append(
            {
                'medicine': matched_medicine,
                'quantity': requirement['quantity'],
            }
        )

    return allocations


def allocate_cart_to_pharmacy(cart, pharmacy):
    requirements = build_cart_requirements(cart)
    pharmacy_medicines = getattr(pharmacy, '_inventory_candidates', None)
    if pharmacy_medicines is None:
        pharmacy_medicines = list(
            Medicine.objects.filter(pharmacy=pharmacy).order_by('-quantity', 'id')
        )
    return allocate_requirements_to_medicines(requirements, pharmacy_medicines)


def get_checkout_candidate_pharmacy_ids(cart):
    requirements = build_cart_requirements(cart)
    if not requirements:
        return []

    candidate_ids = []
    pharmacy_queryset = get_available_pharmacies().prefetch_related(
        Prefetch(
            'medicines',
            queryset=Medicine.objects.order_by('-quantity', 'id'),
            to_attr='_inventory_candidates',
        )
    )

    for pharmacy in pharmacy_queryset:
        if allocate_requirements_to_medicines(
            requirements,
            getattr(pharmacy, '_inventory_candidates', []),
        ) is not None:
            candidate_ids.append(pharmacy.id)

    return candidate_ids


def sync_inventory_for_order_status_transition(order, previous_status, next_status=None):
    next_status = next_status or order.status
    if previous_status == next_status:
        return

    order_items = list(order.items.select_related('medicine').all())
    locked_medicines = {
        medicine.id: medicine
        for medicine in Medicine.objects.select_for_update().filter(
            id__in=[item.medicine_id for item in order_items if item.medicine_id]
        )
    }

    if previous_status != Order.STATUS_CANCELLED and next_status == Order.STATUS_CANCELLED:
        for item in order_items:
            locked_medicine = locked_medicines.get(item.medicine_id)
            if locked_medicine is None:
                continue
            locked_medicine.quantity += item.quantity
            locked_medicine.save(update_fields=['quantity'])
        return

    if previous_status == Order.STATUS_CANCELLED and next_status != Order.STATUS_CANCELLED:
        for item in order_items:
            locked_medicine = locked_medicines.get(item.medicine_id)
            if locked_medicine is None:
                continue
            if locked_medicine.quantity < item.quantity:
                raise ValueError(
                    f"Thuốc '{locked_medicine.name}' không đủ tồn kho để khôi phục đơn #{order.pk}."
                )

        for item in order_items:
            locked_medicine = locked_medicines.get(item.medicine_id)
            if locked_medicine is None:
                continue
            locked_medicine.quantity -= item.quantity
            if locked_medicine.quantity < 0:
                locked_medicine.quantity = 0
            locked_medicine.save(update_fields=['quantity'])


def get_user_role_label(user):
    if user.is_superuser:
        return 'Quản trị viên'
    if user.is_staff:
        return 'Nhân viên quản trị'
    return 'Khách hàng'


def get_medicine_search_queryset(search_keyword=''):
    medicine_queryset = Medicine.objects.select_related('pharmacy').all()

    if search_keyword:
        medicine_queryset = medicine_queryset.filter(
            Q(name__icontains=search_keyword)
            | Q(description__icontains=search_keyword)
            | Q(category__icontains=search_keyword)
            | Q(manufacturer__icontains=search_keyword)
            | Q(usage__icontains=search_keyword)
            | Q(ingredients__icontains=search_keyword)
            | Q(pharmacy__name__icontains=search_keyword)
        )

    return medicine_queryset


def get_popular_categories(limit=8):
    return list(
        Medicine.objects.exclude(category='')
        .values('category')
        .annotate(total=Count('id'))
        .order_by('-total', 'category')[:limit]
    )


def get_featured_pharmacies(limit=3):
    return Pharmacy.objects.annotate(
        available_total=Count('medicines', filter=Q(medicines__quantity__gt=0), distinct=True)
    ).filter(available_total__gt=0).order_by('-available_total', 'name')[:limit]


def get_pharmacy_search_queryset(search_keyword=''):
    pharmacy_queryset = Pharmacy.objects.annotate(
        available_total=Count('medicines', filter=Q(medicines__quantity__gt=0), distinct=True)
    )

    if search_keyword:
        pharmacy_queryset = pharmacy_queryset.filter(
            Q(name__icontains=search_keyword)
            | Q(address__icontains=search_keyword)
            | Q(desc__icontains=search_keyword)
            | Q(phone__icontains=search_keyword)
            | Q(medicines__name__icontains=search_keyword)
            | Q(medicines__category__icontains=search_keyword)
        ).distinct()

    return pharmacy_queryset


def get_available_pharmacies():
    """
    Lấy danh sách nhà thuốc còn ít nhất một loại thuốc có tồn kho.
    """
    return Pharmacy.objects.filter(medicines__quantity__gt=0).distinct()


def build_catalog_search_payload(keyword, medicine_limit=6, pharmacy_limit=6):
    medicines = (
        get_medicine_search_queryset(keyword)
        .order_by('-quantity', Lower('name'), 'id')[:medicine_limit]
    )
    pharmacies = (
        get_pharmacy_search_queryset(keyword)
        .order_by('-available_total', Lower('name'), 'id')[:pharmacy_limit]
    )

    return {
        'query': keyword,
        'products': [
            {
                'id': medicine.id,
                'name': medicine.name,
                'category': medicine.category or 'Thuốc / Dược phẩm',
                'manufacturer': medicine.manufacturer or 'Đang cập nhật',
                'pharmacy_name': medicine.pharmacy.name,
                'price_value': medicine.price,
                'price_text': f"{medicine.price:,} đ".replace(',', '.'),
                'is_in_stock': medicine.is_in_stock,
                'image': medicine.primary_image_url or MEDICINE_FALLBACK_IMAGE,
                'detail_url': reverse('medicine_detail', kwargs={'medicine_id': medicine.id}),
            }
            for medicine in medicines
        ],
        'pharmacies': [
            {
                'id': pharmacy.id,
                'name': pharmacy.name,
                'address': pharmacy.address,
                'phone': pharmacy.phone,
                'available_total': pharmacy.available_total,
                'image': pharmacy.primary_image_url or PHARMACY_FALLBACK_IMAGE,
                'detail_url': reverse('pharmacy_detail', kwargs={'pharmacy_id': pharmacy.id}),
                'map_url': f"{reverse('map_view')}?pharmacy_id={pharmacy.id}",
            }
            for pharmacy in pharmacies
        ],
    }


def build_nearby_pharmacy_payload(lat, lng, radius_km=0, keyword=''):
    try:
        base_lat = float(lat)
        base_lng = float(lng)
    except (TypeError, ValueError):
        raise ValueError('Tọa độ không hợp lệ.')

    try:
        radius_limit = float(radius_km)
    except (TypeError, ValueError):
        radius_limit = 0

    pharmacy_queryset = get_pharmacy_search_queryset(keyword).order_by(Lower('name'), 'id')
    nearby_items = []

    for pharmacy in pharmacy_queryset:
        if pharmacy.lat is None or pharmacy.lng is None:
            continue

        air_distance_km = calculate_air_distance_km(base_lat, base_lng, pharmacy.lat, pharmacy.lng)
        estimated_distance_km = round(estimate_road_distance_km(air_distance_km, 'motorbike'), 2)

        if radius_limit > 0 and estimated_distance_km > radius_limit:
            continue

        nearby_items.append(
            {
                'id': pharmacy.id,
                'name': pharmacy.name,
                'address': pharmacy.address,
                'phone': pharmacy.phone,
                'hours': pharmacy.opening_hours,
                'distance_km': estimated_distance_km,
                'available_total': pharmacy.available_total,
                'image': pharmacy.primary_image_url or PHARMACY_FALLBACK_IMAGE,
                'detail_url': reverse('pharmacy_detail', kwargs={'pharmacy_id': pharmacy.id}),
            }
        )

    nearby_items.sort(key=lambda item: (item['distance_km'], item['name'].casefold(), item['id']))
    return nearby_items


def build_checkout_pharmacy_payload(pharmacy_queryset):
    """
    Chuẩn bị dữ liệu nhà thuốc cho trang checkout.
    """
    checkout_payload = []

    for pharmacy in pharmacy_queryset:
        gallery_images = get_entity_gallery_urls(
            pharmacy,
            PHARMACY_FALLBACK_IMAGE,
        )

        checkout_payload.append(
            {
                'id': pharmacy.id,
                'name': pharmacy.name,
                'address': pharmacy.address,
                'phone': pharmacy.phone,
                'hours': pharmacy.opening_hours,
                'image': gallery_images[0],
                'gallery_images': gallery_images,
                'lat': pharmacy.lat,
                'lng': pharmacy.lng,
            }
        )

    return checkout_payload


def build_map_pharmacy_payload(pharmacy_queryset):
    """
    Chuẩn bị dữ liệu nhà thuốc cho trang bản đồ.
    """
    pharmacy_payload = []

    for pharmacy in pharmacy_queryset:
        gallery_images = get_entity_gallery_urls(
            pharmacy,
            PHARMACY_FALLBACK_IMAGE,
        )

        pharmacy_payload.append(
            {
                'id': pharmacy.id,
                'name': pharmacy.name,
                'address': pharmacy.address,
                'phone': pharmacy.phone,
                'hours': pharmacy.opening_hours,
                'desc': pharmacy.desc,
                'image': gallery_images[0],
                'gallery_images': gallery_images,
                'lat': pharmacy.lat,
                'lng': pharmacy.lng,
            }
        )

    return pharmacy_payload


def estimate_pharmacy_delivery_distance(pharmacy, delivery_lat, delivery_lng, delivery_mode='motorbike'):
    if pharmacy.lat is None or pharmacy.lng is None:
        return None

    air_distance_km = calculate_air_distance_km(
        pharmacy.lat,
        pharmacy.lng,
        delivery_lat,
        delivery_lng,
    )
    return round(estimate_road_distance_km(air_distance_km, delivery_mode), 2)


def rank_pharmacies_by_distance(pharmacies, delivery_lat, delivery_lng, delivery_mode='motorbike'):
    ranked_pharmacies = []

    for pharmacy in pharmacies:
        estimated_distance = estimate_pharmacy_delivery_distance(
            pharmacy,
            delivery_lat,
            delivery_lng,
            delivery_mode,
        )
        if estimated_distance is None:
            continue

        ranked_pharmacies.append((pharmacy, estimated_distance))

    ranked_pharmacies.sort(key=lambda item: (item[1], item[0].name.casefold(), item[0].id))
    return ranked_pharmacies


def choose_checkout_pharmacy(cart, pharmacies, delivery_lat, delivery_lng, delivery_mode='motorbike'):
    ranked_pharmacies = rank_pharmacies_by_distance(
        pharmacies,
        delivery_lat,
        delivery_lng,
        delivery_mode,
    )

    if not ranked_pharmacies:
        return {'error': 'Không tìm được chi nhánh phù hợp cho vị trí đã chọn.'}

    nearest_pharmacy, nearest_distance = ranked_pharmacies[0]

    selected_pharmacy = None
    selected_distance = None
    selected_allocations = []

    if cart.items.exists():
        for pharmacy, distance in ranked_pharmacies:
            allocations = allocate_cart_to_pharmacy(cart, pharmacy)
            if allocations is None:
                continue

            selected_pharmacy = pharmacy
            selected_distance = distance
            selected_allocations = allocations
            break

        if selected_pharmacy is None:
            return {'error': 'Không có chi nhánh nào đủ tồn kho để xử lý toàn bộ giỏ hàng hiện tại.'}
    else:
        selected_pharmacy = nearest_pharmacy
        selected_distance = nearest_distance

    route_result = delivery_service.estimate_route(
        start_lat=selected_pharmacy.lat,
        start_lng=selected_pharmacy.lng,
        end_lat=delivery_lat,
        end_lng=delivery_lng,
        delivery_mode=delivery_mode,
    )
    if 'routes' not in route_result or not route_result['routes']:
        return {'error': 'Không thể tính được tuyến giao hàng cho chi nhánh đã chọn.'}

    notice = ''
    if selected_pharmacy.id != nearest_pharmacy.id:
        notice = (
            f"Chi nhánh gần nhất là {nearest_pharmacy.name} "
            f"({nearest_distance:.1f} km) nhưng chưa đủ thuốc cho toàn bộ đơn hàng. "
            f"Hệ thống đã chuyển sang {selected_pharmacy.name} "
            f"({selected_distance:.1f} km)."
        )

    return {
        'pharmacy': selected_pharmacy,
        'route': route_result['routes'][0],
        'mode': route_result.get('mode', delivery_mode),
        'notice': notice,
        'allocations': selected_allocations,
        'nearest_pharmacy': nearest_pharmacy,
        'nearest_distance_km': nearest_distance,
    }


def find_pharmacy_in_list(pharmacies, pharmacy_id):
    pharmacy_id_text = str(pharmacy_id).strip()
    if not pharmacy_id_text:
        return None

    for pharmacy in pharmacies:
        if str(pharmacy.id) == pharmacy_id_text:
            return pharmacy

    return None


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
    medicines = get_medicine_search_queryset(search_keyword).order_by('-id')
    popular_categories = get_popular_categories(limit=6)
    featured_pharmacies = get_featured_pharmacies(limit=8)

    context = {
        'medicines': medicines[:8] if not search_keyword else medicines,
        'query': search_keyword,
        'popular_categories': popular_categories,
        'featured_pharmacies': featured_pharmacies,
        'featured_medicine_total': medicines.count() if search_keyword else Medicine.objects.count(),
        'available_pharmacy_total': get_available_pharmacies().count(),
    }
    return render(request, 'home.html', context)


def product_list(request):
    """
    Trang danh sách toàn bộ sản phẩm.
    """
    search_keyword = request.GET.get('q', '').strip()
    active_category = request.GET.get('category', '').strip()
    active_pharmacy = request.GET.get('pharmacy', '').strip()
    availability = request.GET.get('availability', 'in_stock').strip() or 'in_stock'
    sort_key = request.GET.get('sort', 'popular').strip() or 'popular'

    medicines = get_medicine_search_queryset(search_keyword)
    if active_category:
        medicines = medicines.filter(category__iexact=active_category)
    if active_pharmacy.isdigit():
        medicines = medicines.filter(pharmacy_id=int(active_pharmacy))
    else:
        active_pharmacy = ''

    if availability == 'in_stock':
        medicines = medicines.filter(quantity__gt=0)
    elif availability != 'all':
        availability = 'in_stock'
        medicines = medicines.filter(quantity__gt=0)

    medicines = medicines.order_by('name', 'unit', 'manufacturer', 'origin', 'price', '-quantity', 'id')

    grouped_products = {}

    for medicine in medicines:
        key = normalize_catalog_key(
            medicine.name,
            medicine.unit,
            medicine.manufacturer,
        )
        branch_entry = {
            'pharmacy_id': medicine.pharmacy_id,
            'pharmacy_name': medicine.pharmacy.name,
            'medicine_id': medicine.id,
            'quantity': medicine.quantity,
            'price_value': medicine.price,
            'price_text': f"{medicine.price:,} đ".replace(',', '.'),
        }

        if key not in grouped_products:
            grouped_products[key] = {
                'id': medicine.id,
                'detail_id': medicine.id,
                'name': medicine.name,
                'category': medicine.category or 'Thuốc / Dược phẩm',
                'unit': medicine.unit or 'Hộp',
                'manufacturer': medicine.manufacturer or 'Đang cập nhật',
                'origin': medicine.origin or 'Đang cập nhật',
                'description': medicine.description or medicine.usage or 'Thông tin sản phẩm đang được cập nhật.',
                'primary_image_url': medicine.primary_image_url or MEDICINE_FALLBACK_IMAGE,
                'is_in_stock': medicine.quantity > 0,
                'min_price_value': medicine.price,
                'max_price_value': medicine.price,
                'branch_count': 0,
                'in_stock_branch_count': 0,
                'total_stock': 0,
                'availability_entries': [],
                '_representative_rank': (
                    0 if medicine.quantity > 0 else 1,
                    medicine.price,
                    medicine.id,
                ),
            }

        product = grouped_products[key]
        product['branch_count'] += 1
        product['min_price_value'] = min(product['min_price_value'], medicine.price)
        product['max_price_value'] = max(product['max_price_value'], medicine.price)

        if medicine.quantity > 0:
            product['is_in_stock'] = True
            product['in_stock_branch_count'] += 1
            product['total_stock'] += medicine.quantity
            product['availability_entries'].append(branch_entry)

        representative_rank = (
            0 if medicine.quantity > 0 else 1,
            medicine.price,
            medicine.id,
        )
        if representative_rank < product['_representative_rank']:
            product['_representative_rank'] = representative_rank
            product['id'] = medicine.id
            product['detail_id'] = medicine.id
            product['description'] = medicine.description or medicine.usage or product['description']
            product['primary_image_url'] = medicine.primary_image_url or product['primary_image_url']

    products = list(grouped_products.values())

    for product in products:
        product['availability_entries'].sort(
            key=lambda item: (-item['quantity'], item['price_value'], item['pharmacy_name'].casefold())
        )
        product['availability_preview'] = product['availability_entries'][:3]
        product['extra_branch_count'] = max(product['in_stock_branch_count'] - len(product['availability_preview']), 0)
        product['min_price_text'] = f"{product['min_price_value']:,} đ".replace(',', '.')
        product['max_price_text'] = f"{product['max_price_value']:,} đ".replace(',', '.')
        del product['_representative_rank']

    if sort_key == 'name':
        products.sort(key=lambda item: (item['name'].casefold(), item['manufacturer'].casefold(), item['id']))
    elif sort_key == 'price_low':
        products.sort(key=lambda item: (item['min_price_value'], item['name'].casefold(), item['id']))
    elif sort_key == 'price_high':
        products.sort(key=lambda item: (-item['max_price_value'], item['name'].casefold(), item['id']))
    elif sort_key == 'stock':
        products.sort(key=lambda item: (-item['total_stock'], -item['in_stock_branch_count'], item['name'].casefold(), item['id']))
    else:
        sort_key = 'popular'
        products.sort(
            key=lambda item: (
                -item['in_stock_branch_count'],
                -item['total_stock'],
                item['min_price_value'],
                item['name'].casefold(),
                item['id'],
            )
        )

    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    pharmacy_options = list(get_available_pharmacies().order_by('name').values('id', 'name'))
    active_pharmacy_name = ''
    if active_pharmacy:
        active_pharmacy_name = next(
            (
                pharmacy['name']
                for pharmacy in pharmacy_options
                if str(pharmacy['id']) == str(active_pharmacy)
            ),
            '',
        )

    return render(
        request,
        'products.html',
        {
            'page_obj': page_obj,
            'products': page_obj.object_list,
            'query': search_keyword,
            'active_category': active_category,
            'active_pharmacy': active_pharmacy,
            'availability': availability,
            'sort_key': sort_key,
            'popular_categories': get_popular_categories(limit=8),
            'pharmacy_options': pharmacy_options,
            'active_pharmacy_name': active_pharmacy_name,
            'available_pharmacy_total': len(pharmacy_options),
            'product_total': paginator.count,
            'current_page_count': len(page_obj.object_list),
            'query_string': query_params.urlencode(),
        }
    )


def medicine_detail(request, medicine_id):
    """
    Trang chi tiết sản phẩm thuốc.
    """
    medicine = get_object_or_404(
        Medicine.objects.select_related('pharmacy'),
        pk=medicine_id,
    )

    related_queryset = Medicine.objects.select_related('pharmacy').exclude(pk=medicine.pk)
    if medicine.category:
        related_queryset = related_queryset.filter(
            Q(category__iexact=medicine.category) | Q(pharmacy=medicine.pharmacy)
        )
    else:
        related_queryset = related_queryset.filter(pharmacy=medicine.pharmacy)

    related_medicines = related_queryset.order_by('-id')[:6]

    same_product_branches = list(
        Medicine.objects.select_related('pharmacy')
        .filter(
            name__iexact=medicine.name,
            unit__iexact=medicine.unit,
            manufacturer__iexact=medicine.manufacturer,
        )
        .order_by('-quantity', 'pharmacy__name', 'id')
    )
    availability_rows = [
        {
            'pharmacy_id': item.pharmacy_id,
            'pharmacy_name': item.pharmacy.name,
            'quantity': item.quantity,
            'price': item.price,
        }
        for item in same_product_branches
        if item.quantity > 0
    ]
    shared_gallery = []
    for item in same_product_branches:
        for image_url in get_entity_gallery_urls(item, MEDICINE_FALLBACK_IMAGE):
            if image_url not in shared_gallery:
                shared_gallery.append(image_url)

    if not shared_gallery:
        shared_gallery = get_entity_gallery_urls(medicine, MEDICINE_FALLBACK_IMAGE)

    system_prices = sorted({item.price for item in same_product_branches})
    availability_summary = {
        'branch_total': len(same_product_branches),
        'in_stock_branch_total': len(availability_rows),
        'total_stock': sum(item['quantity'] for item in availability_rows),
        'rows': availability_rows[:3],
        'extra_branch_count': max(len(availability_rows) - 3, 0),
        'is_price_consistent': len(system_prices) <= 1,
        'system_price_value': system_prices[0] if system_prices else medicine.price,
        'price_min_value': system_prices[0] if system_prices else medicine.price,
        'price_max_value': system_prices[-1] if system_prices else medicine.price,
    }

    cart = get_or_create_cart(request)
    cart_item = cart.items.filter(medicine=medicine).first()

    return render(
        request,
        'medicine_detail.html',
        {
            'medicine': medicine,
            'medicine_gallery': shared_gallery,
            'medicine_fallback_image': MEDICINE_FALLBACK_IMAGE,
            'related_medicines': related_medicines,
            'availability_summary': availability_summary,
            'cart_item': cart_item,
        }
    )


def pharmacy_detail(request, pharmacy_id):
    """
    Trang chi tiết một nhà thuốc.
    """
    pharmacy = get_object_or_404(Pharmacy, pk=pharmacy_id)
    medicines = Medicine.objects.filter(pharmacy=pharmacy).order_by('name')
    has_stock = medicines.filter(quantity__gt=0).exists()

    return render(request, 'pharmacy_detail.html', {
        'pharmacy': pharmacy,
        'pharmacy_gallery': get_entity_gallery_urls(
            pharmacy,
            PHARMACY_FALLBACK_IMAGE,
        ),
        'medicines': medicines,
        'has_stock': has_stock,
        'popular_categories': get_popular_categories(limit=6),
    })


def add_to_cart(request, medicine_id):
    """
    Thêm sản phẩm vào giỏ hàng.
    - GET: thêm nhanh 1 sản phẩm
    - POST: thêm theo số lượng từ trang chi tiết
    """
    medicine = get_object_or_404(Medicine, id=medicine_id)
    cart = get_or_create_cart(request)

    quantity_raw = request.POST.get('quantity') or request.GET.get('quantity') or '1'
    buy_now = request.POST.get('buy_now') or request.GET.get('buy_now')

    try:
        quantity_to_add = int(quantity_raw)
    except (TypeError, ValueError):
        quantity_to_add = 1

    if quantity_to_add < 1:
        quantity_to_add = 1

    fallback_url = request.META.get('HTTP_REFERER')
    expects_json = request_expects_json(request)

    if medicine.quantity <= 0:
        message_text = f"Thuốc '{medicine.name}' hiện đã hết hàng."
        if expects_json:
            return JsonResponse({'message': message_text, 'cart_items_count': get_cart_items_count(cart)}, status=400)
        messages.error(request, message_text)
        if fallback_url:
            return redirect(fallback_url)
        return redirect('medicine_detail', medicine_id=medicine.id)

    cart_item, created = CartItem.objects.get_or_create(cart=cart, medicine=medicine)
    current_quantity = 0 if created else cart_item.quantity
    new_quantity = current_quantity + quantity_to_add

    if new_quantity > medicine.quantity:
        message_text = f"Thuốc '{medicine.name}' chỉ còn {medicine.quantity} sản phẩm trong kho."
        if expects_json:
            return JsonResponse({'message': message_text, 'cart_items_count': get_cart_items_count(cart)}, status=400)
        messages.error(request, message_text)
        if fallback_url:
            return redirect(fallback_url)
        return redirect('medicine_detail', medicine_id=medicine.id)

    cart_item.quantity = new_quantity
    cart_item.save()

    if buy_now:
        message_text = f"Đã thêm '{medicine.name}' vào giỏ và chuyển sang thanh toán."
        if expects_json:
            return JsonResponse(
                {
                    'message': message_text,
                    'cart_items_count': get_cart_items_count(cart),
                    'redirect_url': reverse('checkout'),
                }
            )
        messages.success(request, message_text)
        return redirect('checkout')

    message_text = f"Đã thêm '{medicine.name}' vào giỏ hàng."
    if expects_json:
        return JsonResponse(
            {
                'message': message_text,
                'cart_items_count': get_cart_items_count(cart),
            }
        )
    messages.success(request, message_text)
    if fallback_url:
        return redirect(fallback_url)
    return redirect('medicine_detail', medicine_id=medicine.id)


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
        messages.warning(request, 'Bạn cần có sản phẩm trong giỏ hàng trước khi thanh toán.')
        return redirect('cart_detail')

    available_pharmacies = list(
        get_available_pharmacies().prefetch_related(
            Prefetch(
                'medicines',
                queryset=Medicine.objects.order_by('-quantity', 'id'),
                to_attr='_inventory_candidates',
            )
        )
    )
    if not available_pharmacies:
        messages.error(request, 'Hiện chưa có chi nhánh khả dụng để xử lý đơn hàng.')
        return redirect('cart_detail')

    has_fulfillment_branch = any(
        allocate_cart_to_pharmacy(cart, pharmacy) is not None
        for pharmacy in available_pharmacies
    )
    if not has_fulfillment_branch:
        messages.error(request, 'Không có chi nhánh nào đủ tồn kho để xử lý toàn bộ giỏ hàng hiện tại.')
        return redirect('cart_detail')

    pharmacy_payload = build_checkout_pharmacy_payload(available_pharmacies)
    profile = get_or_create_user_profile(request.user) if request.user.is_authenticated else None
    saved_address = build_saved_address_payload(profile) if profile and is_customer_user(request.user) else None
    requested_address = (request.POST.get('address_text') or request.GET.get('address') or '').strip()
    requested_pharmacy_id = (request.POST.get('pharmacy_id') or request.GET.get('pharmacy_id') or '').strip()
    requested_lat = (request.POST.get('delivery_lat') or request.GET.get('delivery_lat') or '').strip()
    requested_lng = (request.POST.get('delivery_lng') or request.GET.get('delivery_lng') or '').strip()

    def build_checkout_context(form_instance):
        preselected_delivery = None

        if requested_lat and requested_lng:
            try:
                preselected_delivery = {
                    'lat': float(requested_lat),
                    'lng': float(requested_lng),
                    'address_text': requested_address,
                }
            except (TypeError, ValueError):
                preselected_delivery = None
        elif saved_address and saved_address.get('lat') is not None and saved_address.get('lng') is not None:
            preselected_delivery = saved_address

        return {
            'form': form_instance,
            'cart': cart,
            'pharmacies': pharmacy_payload,
            'saved_address': saved_address,
            'preselected_delivery': preselected_delivery,
            'preselected_pharmacy_id': requested_pharmacy_id,
        }

    if request.method == 'POST':
        form = CheckoutForm(request.POST)

        if not form.is_valid():
            messages.error(request, 'Thông tin chưa hợp lệ. Vui lòng kiểm tra lại biểu mẫu.')
            return render(request, 'checkout.html', build_checkout_context(form))

        delivery_lat = request.POST.get('delivery_lat', '').strip()
        delivery_lng = request.POST.get('delivery_lng', '').strip()
        selected_pharmacy_id = request.POST.get('pharmacy_id', '').strip()

        if not delivery_lat or not delivery_lng:
            messages.error(request, 'Vui lòng chọn vị trí giao hàng trên bản đồ để hệ thống tính chi nhánh và phí ship.')
            return render(request, 'checkout.html', build_checkout_context(form))

        best_delivery_result = None

        if selected_pharmacy_id:
            selected_pharmacy = find_pharmacy_in_list(available_pharmacies, selected_pharmacy_id)
            selected_allocations = allocate_cart_to_pharmacy(cart, selected_pharmacy) if selected_pharmacy else None

            if selected_pharmacy and selected_allocations is not None:
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
                        'allocations': selected_allocations,
                        'notice': '',
                    }

        if best_delivery_result is None:
            best_delivery_result = choose_checkout_pharmacy(
                cart,
                available_pharmacies,
                delivery_lat,
                delivery_lng,
                'motorbike',
            )

        if 'error' in best_delivery_result:
            messages.error(request, best_delivery_result['error'])
            return render(request, 'checkout.html', build_checkout_context(form))

        selected_pharmacy = best_delivery_result['pharmacy']
        selected_route = best_delivery_result['route']
        selected_allocations = best_delivery_result.get('allocations')
        if selected_allocations is None:
            selected_allocations = allocate_cart_to_pharmacy(cart, selected_pharmacy)

        if selected_allocations is None:
            messages.error(request, 'Chi nhánh được chọn không còn đủ tồn kho cho giỏ hàng hiện tại.')
            return redirect('cart_detail')

        try:
            with transaction.atomic():
                locked_medicines = {
                    medicine.id: medicine
                    for medicine in Medicine.objects.select_for_update().select_related('pharmacy').filter(
                        id__in=[allocation['medicine'].id for allocation in selected_allocations]
                    )
                }
                finalized_allocations = []

                for allocation in selected_allocations:
                    locked_medicine = locked_medicines.get(allocation['medicine'].id)
                    quantity = allocation['quantity']

                    if locked_medicine is None:
                        raise ValueError('Một số sản phẩm trong giỏ không còn khả dụng.')

                    if quantity > locked_medicine.quantity:
                        raise ValueError(
                            f"Thuốc '{locked_medicine.name}' tại {locked_medicine.pharmacy.name} chỉ còn {locked_medicine.quantity} {locked_medicine.unit.lower()}."
                        )

                    finalized_allocations.append({
                        'medicine': locked_medicine,
                        'quantity': quantity,
                    })

                selected_total_product_price = sum(
                    allocation['medicine'].price * allocation['quantity']
                    for allocation in finalized_allocations
                )

                order = form.save(commit=False)

                if request.user.is_authenticated:
                    order.user = request.user

                order.delivery_lat = float(delivery_lat)
                order.delivery_lng = float(delivery_lng)
                order.pharmacy = selected_pharmacy
                order.distance_km = selected_route['distance_km']
                order.shipping_fee = selected_route['shipping_fee_value']
                order.total_product_price = selected_total_product_price
                order.final_total_price = selected_total_product_price + order.shipping_fee
                order.save()
                update_profile_from_checkout(request.user, order)

                for allocation in finalized_allocations:
                    medicine = allocation['medicine']
                    quantity = allocation['quantity']

                    OrderItem.objects.create(
                        order=order,
                        medicine=medicine,
                        medicine_name=medicine.name,
                        price=medicine.price,
                        quantity=quantity,
                    )

                    medicine.quantity -= quantity
                    if medicine.quantity < 0:
                        medicine.quantity = 0
                    medicine.save(update_fields=['quantity'])

                cart.items.all().delete()

                transaction.on_commit(
                    lambda confirmed_order=order, current_request=request: (
                        send_order_confirmation_email(confirmed_order, request=current_request),
                        send_order_invoice_email(confirmed_order, request=current_request),
                    )
                )
        except ValueError as exc:
            messages.error(request, f"{exc} Vui lòng kiểm tra lại giỏ hàng.")
            return redirect('checkout')

        messages.success(request, 'Đặt hàng thành công.')
        if best_delivery_result.get('notice'):
            messages.info(request, best_delivery_result['notice'])
        return redirect('order_history')

    initial_data = {}
    if profile:
        initial_data = {
            'full_name': profile.full_name or request.user.get_full_name() or request.user.username,
            'phone': profile.phone,
            'address_text': requested_address or profile.address_text,
        }
    elif requested_address:
        initial_data['address_text'] = requested_address

    form = CheckoutForm(initial=initial_data)
    return render(request, 'checkout.html', build_checkout_context(form))


def checkout_page(request):
    return checkout(request)


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
            get_or_create_user_profile(user)
            login(request, user)
            return redirect(get_safe_redirect_url(request, default='account'))
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
                return redirect(get_safe_redirect_url(request, default='account'))

            form.add_error(None, 'Tên đăng nhập hoặc mật khẩu không đúng.')
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
def account_view(request):
    profile = get_or_create_user_profile(request.user)
    is_customer = is_customer_user(request.user)
    user_orders = Order.objects.filter(user=request.user)
    recent_orders = user_orders.select_related('pharmacy').prefetch_related('items').order_by('-created_at', '-id')[:3]
    cart = get_or_create_cart(request)

    if request.method == 'POST':
        form = AccountProfileForm(
            request.POST,
            user=request.user,
            profile=profile,
            is_customer=is_customer,
        )
        if form.is_valid():
            full_name = (form.cleaned_data.get('full_name') or '').strip()
            request.user.email = form.cleaned_data.get('email') or ''
            request.user.first_name = full_name
            request.user.last_name = ''
            request.user.save(update_fields=['email', 'first_name', 'last_name'])

            profile.full_name = full_name
            profile.phone = (form.cleaned_data.get('phone') or '').strip()

            if is_customer:
                profile.address_text = (form.cleaned_data.get('address_text') or '').strip()
                profile.address_lat = form.cleaned_data.get('address_lat')
                profile.address_lng = form.cleaned_data.get('address_lng')

                if profile.address_text and (profile.address_lat is None or profile.address_lng is None):
                    try:
                        first_match = search_address_candidates(profile.address_text, limit=1)
                    except Exception:
                        first_match = []

                    if first_match:
                        profile.address_lat = first_match[0]['lat']
                        profile.address_lng = first_match[0]['lng']
                elif not profile.address_text:
                    profile.address_lat = None
                    profile.address_lng = None

            profile.save()
            messages.success(request, 'Đã cập nhật thông tin tài khoản.')
            return redirect('account')
    else:
        form = AccountProfileForm(
            user=request.user,
            profile=profile,
            is_customer=is_customer,
        )

    context = {
        'account_role': get_user_role_label(request.user),
        'orders_total': user_orders.count(),
        'orders_pending': user_orders.filter(status=Order.STATUS_PENDING).count(),
        'orders_completed': user_orders.filter(status=Order.STATUS_COMPLETED).count(),
        'recent_orders': recent_orders,
        'cart_items_total': get_cart_items_count(cart),
        'account_form': form,
        'profile': profile,
        'is_customer': is_customer,
        'saved_address': build_saved_address_payload(profile),
    }
    return render(request, 'account.html', context)


@login_required(login_url='/login/')
def order_history(request):
    """
    Hiển thị lịch sử đơn hàng của người dùng đang đăng nhập.
    """
    orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at', '-id')
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
    selected_pharmacy_id = request.GET.get('pharmacy_id', '').strip()

    if not all([delivery_lat, delivery_lng]):
        return JsonResponse({'error': 'Thiếu tọa độ giao hàng.'}, status=400)

    available_pharmacies = get_available_pharmacies()

    if selected_pharmacy_id:
        selected_pharmacy = find_pharmacy_in_list(available_pharmacies, selected_pharmacy_id)
        if selected_pharmacy:
            route_result = delivery_service.estimate_route(
                start_lat=selected_pharmacy.lat,
                start_lng=selected_pharmacy.lng,
                end_lat=delivery_lat,
                end_lng=delivery_lng,
                delivery_mode=delivery_mode,
            )
            if 'routes' in route_result and route_result['routes']:
                best_delivery_result = {
                    'pharmacy': selected_pharmacy,
                    'route': route_result['routes'][0],
                    'mode': route_result.get('mode', delivery_mode),
                }
            else:
                best_delivery_result = {'error': 'Không thể tính được đường đi cho chi nhánh đã chọn.'}
        else:
            best_delivery_result = {'error': 'Không tìm thấy chi nhánh đã chọn.'}
    else:
        best_delivery_result = choose_checkout_pharmacy(
            cart,
            available_pharmacies,
            delivery_lat,
            delivery_lng,
            delivery_mode,
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
            'hours': selected_pharmacy.opening_hours,
            'image': get_entity_gallery_urls(
                selected_pharmacy,
                PHARMACY_FALLBACK_IMAGE,
            )[0],
            'lat': selected_pharmacy.lat,
            'lng': selected_pharmacy.lng,
        },
        'route': best_delivery_result['route'],
        'mode': best_delivery_result.get('mode', delivery_mode),
    }

    return JsonResponse(response_data)


def find_best_pharmacy_api_v2(request):
    delivery_lat = request.GET.get('delivery_lat')
    delivery_lng = request.GET.get('delivery_lng')
    delivery_mode = request.GET.get('mode', 'motorbike')
    selected_pharmacy_id = request.GET.get('pharmacy_id', '').strip()

    if not all([delivery_lat, delivery_lng]):
        return JsonResponse({'error': 'Thiếu tọa độ giao hàng.'}, status=400)

    cart = get_or_create_cart(request)
    available_pharmacies = list(
        get_available_pharmacies().prefetch_related(
            Prefetch(
                'medicines',
                queryset=Medicine.objects.order_by('-quantity', 'id'),
                to_attr='_inventory_candidates',
            )
        )
    )

    if not available_pharmacies:
        return JsonResponse({'error': 'Không có chi nhánh phù hợp cho giỏ hàng hiện tại.'}, status=400)

    if selected_pharmacy_id:
        selected_pharmacy = find_pharmacy_in_list(available_pharmacies, selected_pharmacy_id)
        if not selected_pharmacy:
            return JsonResponse({'error': 'Không tìm thấy chi nhánh đã chọn.'}, status=400)
        if cart.items.exists() and allocate_cart_to_pharmacy(cart, selected_pharmacy) is None:
            return JsonResponse(
                {'error': 'Chi nhánh đã chọn chưa đủ thuốc cho toàn bộ đơn hàng.'},
                status=400,
            )

        route_result = delivery_service.estimate_route(
            start_lat=selected_pharmacy.lat,
            start_lng=selected_pharmacy.lng,
            end_lat=delivery_lat,
            end_lng=delivery_lng,
            delivery_mode=delivery_mode,
        )
        if 'routes' not in route_result or not route_result['routes']:
            return JsonResponse({'error': 'Không thể tính được đường đi cho chi nhánh đã chọn.'}, status=400)

        best_delivery_result = {
            'pharmacy': selected_pharmacy,
            'route': route_result['routes'][0],
            'mode': route_result.get('mode', delivery_mode),
            'notice': '',
        }
    else:
        best_delivery_result = choose_checkout_pharmacy(
            cart,
            available_pharmacies,
            delivery_lat,
            delivery_lng,
            delivery_mode,
        )

    if 'error' in best_delivery_result:
        return JsonResponse(best_delivery_result, status=400)

    selected_pharmacy = best_delivery_result['pharmacy']
    selected_allocations = best_delivery_result.get('allocations')
    if selected_allocations is None:
        selected_allocations = allocate_cart_to_pharmacy(cart, selected_pharmacy) if cart.items.exists() else []
    product_total_value = sum(
        allocation['medicine'].price * allocation['quantity']
        for allocation in selected_allocations
    )
    response_data = {
        'pharmacy': {
            'id': selected_pharmacy.id,
            'name': selected_pharmacy.name,
            'address': selected_pharmacy.address,
            'phone': selected_pharmacy.phone,
            'hours': selected_pharmacy.opening_hours,
            'image': get_entity_gallery_urls(selected_pharmacy, PHARMACY_FALLBACK_IMAGE)[0],
            'lat': selected_pharmacy.lat,
            'lng': selected_pharmacy.lng,
        },
        'route': best_delivery_result['route'],
        'mode': best_delivery_result.get('mode', delivery_mode),
        'product_total_value': product_total_value,
        'notice': best_delivery_result.get('notice', ''),
    }
    return JsonResponse(response_data)


def catalog_search_api(request):
    keyword = request.GET.get('q', '').strip()

    if not keyword:
        return JsonResponse(
            {
                'query': '',
                'products': [],
                'pharmacies': [],
            }
        )

    payload = build_catalog_search_payload(keyword)
    payload['product_total'] = len(payload['products'])
    payload['pharmacy_total'] = len(payload['pharmacies'])
    return JsonResponse(payload)


def nearby_pharmacies_api(request):
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radius = request.GET.get('radius', '0')
    keyword = request.GET.get('q', '').strip()

    if not lat or not lng:
        return JsonResponse({'error': 'Thiếu tọa độ để lọc bán kính.'}, status=400)

    try:
        nearby_items = build_nearby_pharmacy_payload(lat, lng, radius_km=radius, keyword=keyword)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    try:
        radius_value = float(radius or 0)
    except (TypeError, ValueError):
        radius_value = 0

    return JsonResponse(
        {
            'lat': float(lat),
            'lng': float(lng),
            'radius_km': radius_value,
            'query': keyword,
            'pharmacies': nearby_items,
            'total': len(nearby_items),
        }
    )


def search_address_api(request):
    """
    API tìm kiếm địa chỉ cho các trang bản đồ.
    """
    keyword = request.GET.get('q', '').strip()

    if not keyword:
        return JsonResponse({'error': 'Vui lòng nhập địa chỉ cần tìm.'}, status=400)

    try:
        results = search_address_candidates(keyword)
    except Exception:
        return JsonResponse({'error': 'Không kết nối được dịch vụ tìm địa chỉ.'}, status=502)

    return JsonResponse({
        'query': keyword,
        'results': results,
    })


def reverse_address_api(request):
    """
    API lấy địa chỉ từ tọa độ trên bản đồ.
    """
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')

    if not lat or not lng:
        return JsonResponse({'error': 'Thiếu tọa độ để tìm địa chỉ.'}, status=400)

    try:
        result = reverse_geocode_coordinates(lat, lng)
    except Exception:
        return JsonResponse({'error': 'Không kết nối được dịch vụ tra cứu địa chỉ.'}, status=502)

    return JsonResponse({
        'address': result.get('display_name', ''),
        'lat': result.get('lat'),
        'lng': result.get('lng'),
    })


@login_required(login_url='/login/')
def save_profile_address_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Phương thức không hợp lệ.'}, status=405)

    if not is_customer_user(request.user):
        return JsonResponse({'error': 'Chỉ tài khoản khách hàng mới có thể lưu địa chỉ giao hàng.'}, status=403)

    profile = get_or_create_user_profile(request.user)
    address_text = (request.POST.get('address_text') or '').strip()
    lat = request.POST.get('lat')
    lng = request.POST.get('lng')

    profile.address_text = address_text

    if address_text and lat and lng:
        try:
            profile.address_lat = float(lat)
            profile.address_lng = float(lng)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Tọa độ không hợp lệ.'}, status=400)
    elif not address_text:
        profile.address_lat = None
        profile.address_lng = None

    profile.save()
    return JsonResponse({'saved': True})


def map_view(request):
    """
    Trang bản đồ hiển thị danh sách các nhà thuốc còn hàng.
    """
    pharmacies = get_available_pharmacies()
    pharmacy_payload = build_map_pharmacy_payload(pharmacies)
    saved_address = None
    selected_pharmacy_id = request.GET.get('pharmacy_id', '').strip() or request.GET.get('pharmacy', '').strip()
    if is_customer_user(request.user):
        saved_address = build_saved_address_payload(get_or_create_user_profile(request.user))
    return render(
        request,
        'map.html',
        {
            'pharmacies': pharmacy_payload,
            'saved_address': saved_address,
            'selected_pharmacy_id': selected_pharmacy_id,
        },
    )


# =========================================================
# CUSTOM ADMIN PANEL
# =========================================================

LOW_STOCK_THRESHOLD = 10
ADMIN_PAGE_SIZE = 5


def staff_check(user):
    return user.is_authenticated and user.is_staff


def get_object_label(obj):
    if hasattr(obj, 'name') and obj.name:
        return obj.name
    if hasattr(obj, 'username') and obj.username:
        return obj.username
    if hasattr(obj, 'full_name') and obj.full_name:
        return obj.full_name
    return f'#{obj.pk}'


def build_search_query(keyword, fields):
    query = Q()
    for field in fields:
        query |= Q(**{f'{field}__icontains': keyword})
    return query


def format_money(value):
    try:
        return f"{int(value):,}".replace(',', '.') + ' đ'
    except (TypeError, ValueError):
        return '0 đ'


def render_badge(label, tone='secondary'):
    return format_html('<span class="admin-badge admin-badge-{}">{}</span>', tone, label)


def render_image_thumb(image_field, alt_text, empty_text='Chưa có ảnh'):
    if image_field:
        return format_html(
            '<div class="table-thumb-wrap"><img src="{}" alt="{}" class="table-thumb"></div>',
            image_field.url,
            alt_text,
        )
    return format_html(
        '<div class="table-thumb table-thumb-empty"><i class="fas fa-image"></i><span>{}</span></div>',
        empty_text,
    )


def render_stock_badge(quantity):
    if quantity <= 0:
        return render_badge('Hết hàng', 'danger')
    if quantity <= LOW_STOCK_THRESHOLD:
        return render_badge('Sắp hết', 'warning')
    return render_badge('Còn hàng', 'success')


def render_prescription_badge(required):
    return render_badge('Cần kê đơn', 'info') if required else render_badge('Không kê đơn', 'success')


def render_order_status_badge(status):
    mapping = {
        Order.STATUS_PENDING: ('Chờ xử lý', 'warning'),
        Order.STATUS_SHIPPING: ('Đang giao', 'info'),
        Order.STATUS_COMPLETED: ('Hoàn thành', 'success'),
        Order.STATUS_CANCELLED: ('Đã hủy', 'danger'),
    }
    label, tone = mapping.get(status, ('Không xác định', 'secondary'))
    return render_badge(label, tone)


def render_user_role_badge(user):
    if user.is_superuser:
        return render_badge('Superuser', 'danger')
    if user.is_staff:
        return render_badge('Nhân viên', 'info')
    return render_badge('Khách hàng', 'secondary')


def can_delete_object(request_user, model_key, obj=None):
    if not request_user.is_superuser:
        return False
    if model_key == 'user' and obj and obj == request_user:
        return False
    return True


def can_access_admin_model(user, model_key):
    if not user.is_authenticated or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    return model_key in {'medicine', 'order'}


def require_admin_model_access(request, model_key):
    if can_access_admin_model(request.user, model_key):
        return None
    messages.error(request, 'Tài khoản nhân viên không có quyền truy cập chức năng này.')
    return redirect('custom_admin_dashboard')


ADMIN_MODELS = {
    'pharmacy': {
        'model': Pharmacy,
        'title': 'Chi nhánh',
        'title_plural': 'Chi nhánh',
        'form_create': PharmacyAdminForm,
        'form_update': PharmacyAdminForm,
        'search_fields': ['name', 'address', 'phone', 'desc'],
    },
    'medicine': {
        'model': Medicine,
        'title': 'Sản phẩm thuốc',
        'title_plural': 'Sản phẩm thuốc',
        'form_create': MedicineAdminForm,
        'form_update': MedicineAdminForm,
        'search_fields': ['name', 'category', 'manufacturer', 'origin', 'pharmacy__name'],
    },
    'order': {
        'model': Order,
        'title': 'Đơn hàng',
        'title_plural': 'Đơn hàng',
        'search_fields': ['full_name', 'phone', 'address_text', 'pharmacy__name'],
    },
    'user': {
        'model': User,
        'title': 'Tài khoản',
        'title_plural': 'Tài khoản',
        'form_create': CustomUserCreateForm,
        'form_update': CustomUserUpdateForm,
        'search_fields': ['username', 'email', 'first_name', 'last_name'],
    },
}


def get_admin_config(model_key):
    config = ADMIN_MODELS.get(model_key)
    if not config:
        raise Http404('Không tìm thấy module quản trị')
    return config


def get_admin_form_sections(form, model_key):
    layouts = {
        'pharmacy': [
            {
                'title': 'Thông tin chi nhánh',
                'icon': 'fas fa-clinic-medical',
                'fields': ['name', 'address', 'phone', 'desc'],
            },
            {
                'title': 'Thời gian hoạt động và bản đồ',
                'icon': 'fas fa-clock',
                'fields': ['open_time', 'close_time', 'lat', 'lng'],
            },
            {
                'title': 'Hình ảnh đại diện',
                'icon': 'fas fa-image',
                'fields': ['image', 'gallery_images'],
            },
        ],
        'medicine': [
            {
                'title': 'Thông tin cơ bản',
                'icon': 'fas fa-pills',
                'fields': ['name', 'pharmacy', 'category', 'unit', 'description', 'image', 'gallery_images'],
            },
            {
                'title': 'Thông tin bán hàng',
                'icon': 'fas fa-cash-register',
                'fields': ['price', 'quantity', 'prescription_required'],
            },
            {
                'title': 'Thông tin chuyên môn',
                'icon': 'fas fa-notes-medical',
                'fields': ['usage', 'ingredients', 'dosage'],
            },
            {
                'title': 'Nguồn gốc sản phẩm',
                'icon': 'fas fa-industry',
                'fields': ['manufacturer', 'origin'],
            },
        ],
        'user': [
            {
                'title': 'Thông tin đăng nhập',
                'icon': 'fas fa-user-shield',
                'fields': ['username', 'email'],
            },
            {
                'title': 'Thông tin cá nhân',
                'icon': 'fas fa-id-card',
                'fields': ['first_name', 'last_name'],
            },
            {
                'title': 'Bảo mật tài khoản',
                'icon': 'fas fa-lock',
                'fields': ['password1', 'password2', 'new_password', 'confirm_new_password'],
            },
            {
                'title': 'Phân quyền',
                'icon': 'fas fa-user-cog',
                'fields': ['role', 'is_active'],
            },
        ],
    }

    sections = []
    for section in layouts.get(model_key, []):
        normal_fields = []
        checkbox_fields = []
        for field_name in section['fields']:
            if field_name not in form.fields:
                continue
            bound_field = form[field_name]
            input_type = getattr(bound_field.field.widget, 'input_type', '')
            field_info = {
                'field': bound_field,
                'full_width': input_type in {'textarea', 'file'} or field_name in {'desc', 'description', 'usage', 'ingredients', 'dosage'},
            }
            if input_type == 'checkbox':
                checkbox_fields.append(field_info)
            else:
                normal_fields.append(field_info)
        if normal_fields or checkbox_fields:
            sections.append({
                'title': section['title'],
                'icon': section['icon'],
                'normal_fields': normal_fields,
                'checkbox_fields': checkbox_fields,
            })
    return sections


def apply_admin_sort(queryset, model_key, sort_key):
    sort_map = {
        'pharmacy': {
            'newest': '-id',
            'name_asc': 'name',
            'name_desc': '-name',
            'medicine_desc': '-medicine_total',
        },
        'medicine': {
            'newest': '-id',
            'name_asc': 'name',
            'price_low': 'price',
            'price_high': '-price',
            'stock_low': 'quantity',
            'stock_high': '-quantity',
        },
        'order': {
            'newest': ('-created_at', '-id'),
            'oldest': ('created_at', 'id'),
            'total_high': '-final_total_price',
            'total_low': 'final_total_price',
        },
        'user': {
            'newest': '-date_joined',
            'username_asc': 'username',
            'username_desc': '-username',
        },
    }
    selected = sort_map.get(model_key, {}).get(sort_key)
    if isinstance(selected, (list, tuple)):
        return queryset.order_by(*selected)
    return queryset.order_by(selected or '-id')


def get_pharmacy_filter_options(request):
    return [
        {
            'name': 'stock_state',
            'label': 'Tình trạng',
            'value': request.GET.get('stock_state', ''),
            'options': [
                ('', 'Tất cả'),
                ('available', 'Có hàng'),
                ('empty', 'Không có hàng'),
            ],
        },
        {
            'name': 'sort',
            'label': 'Sắp xếp',
            'value': request.GET.get('sort', 'name_asc'),
            'options': [
                ('name_asc', 'Tên A-Z'),
                ('name_desc', 'Tên Z-A'),
                ('medicine_desc', 'Nhiều sản phẩm nhất'),
                ('newest', 'Mới cập nhật'),
            ],
        },
    ]


def get_medicine_filter_options(request):
    pharmacy_id = request.GET.get('pharmacy', '')
    return [
        {
            'name': 'pharmacy',
            'label': 'Chi nhánh',
            'value': pharmacy_id,
            'options': [('', 'Tất cả')] + [(str(pharmacy.pk), pharmacy.name) for pharmacy in Pharmacy.objects.order_by('name')],
        },
        {
            'name': 'stock',
            'label': 'Tồn kho',
            'value': request.GET.get('stock', ''),
            'options': [
                ('', 'Tất cả'),
                ('in', 'Còn hàng'),
                ('low', 'Sắp hết'),
                ('out', 'Hết hàng'),
            ],
        },
        {
            'name': 'rx',
            'label': 'Kê đơn',
            'value': request.GET.get('rx', ''),
            'options': [
                ('', 'Tất cả'),
                ('yes', 'Cần kê đơn'),
                ('no', 'Không kê đơn'),
            ],
        },
        {
            'name': 'sort',
            'label': 'Sắp xếp',
            'value': request.GET.get('sort', 'newest'),
            'options': [
                ('newest', 'Mới nhất'),
                ('name_asc', 'Tên A-Z'),
                ('price_low', 'Giá tăng dần'),
                ('price_high', 'Giá giảm dần'),
                ('stock_low', 'Tồn kho thấp nhất'),
                ('stock_high', 'Tồn kho cao nhất'),
            ],
        },
    ]


def get_order_filter_options(request):
    pharmacy_id = request.GET.get('pharmacy', '')
    return [
        {
            'name': 'status',
            'label': 'Trạng thái',
            'value': request.GET.get('status', ''),
            'options': [('', 'Tất cả')] + [(value, label) for value, label in Order.STATUS_CHOICES],
        },
        {
            'name': 'pharmacy',
            'label': 'Chi nhánh',
            'value': pharmacy_id,
            'options': [('', 'Tất cả')] + [(str(pharmacy.pk), pharmacy.name) for pharmacy in Pharmacy.objects.order_by('name')],
        },
        {
            'name': 'sort',
            'label': 'Sắp xếp',
            'value': request.GET.get('sort', 'newest'),
            'options': [
                ('newest', 'Mới nhất'),
                ('oldest', 'Cũ nhất'),
                ('total_high', 'Tổng tiền giảm dần'),
                ('total_low', 'Tổng tiền tăng dần'),
            ],
        },
    ]


def get_user_filter_options(request):
    return [
        {
            'name': 'role',
            'label': 'Vai trò',
            'value': request.GET.get('role', ''),
            'options': [
                ('', 'Tất cả'),
                ('customer', 'Khách hàng'),
                ('staff', 'Nhân viên'),
                ('superuser', 'Superuser'),
            ],
        },
        {
            'name': 'active',
            'label': 'Trạng thái',
            'value': request.GET.get('active', ''),
            'options': [
                ('', 'Tất cả'),
                ('yes', 'Đang hoạt động'),
                ('no', 'Đã khóa'),
            ],
        },
        {
            'name': 'sort',
            'label': 'Sắp xếp',
            'value': request.GET.get('sort', 'newest'),
            'options': [
                ('newest', 'Mới nhất'),
                ('username_asc', 'Tên đăng nhập A-Z'),
                ('username_desc', 'Tên đăng nhập Z-A'),
            ],
        },
    ]


def build_list_data(model_key, request):
    keyword = request.GET.get('q', '').strip()

    if model_key == 'pharmacy':
        queryset = Pharmacy.objects.annotate(
            medicine_total=Count('medicines', distinct=True),
            available_total=Count('medicines', filter=Q(medicines__quantity__gt=0), distinct=True),
        )
        if keyword:
            queryset = queryset.filter(build_search_query(keyword, ADMIN_MODELS[model_key]['search_fields']))

        stock_state = request.GET.get('stock_state', '')
        if stock_state == 'available':
            queryset = queryset.filter(available_total__gt=0)
        elif stock_state == 'empty':
            queryset = queryset.filter(available_total=0)

        queryset = apply_admin_sort(queryset, model_key, request.GET.get('sort', 'name_asc'))
        columns = ['Ảnh', 'Chi nhánh', 'Liên hệ', 'Giờ hoạt động', 'Sản phẩm', 'Tình trạng']
        summary_cards = [
            {'label': 'Tổng chi nhánh', 'value': Pharmacy.objects.count(), 'tone': 'primary'},
            {'label': 'Chi nhánh có hàng', 'value': Pharmacy.objects.filter(medicines__quantity__gt=0).distinct().count(), 'tone': 'success'},
            {'label': 'Chi nhánh chưa có hàng', 'value': queryset.filter(available_total=0).count(), 'tone': 'warning'},
        ]
        filter_options = get_pharmacy_filter_options(request)

        rows = []
        for obj in queryset:
            status_badge = render_badge('Có hàng', 'success') if obj.available_total > 0 else render_badge('Không có hàng', 'danger')
            actions = [
                {'url': reverse('custom_admin_update', kwargs={'model_key': 'pharmacy', 'pk': obj.pk}), 'label': 'Cập nhật', 'icon': 'fas fa-pen', 'class': 'btn-primary'},
            ]
            if can_delete_object(request.user, model_key, obj):
                actions.append({'url': reverse('custom_admin_delete', kwargs={'model_key': 'pharmacy', 'pk': obj.pk}), 'label': 'Xóa', 'icon': 'fas fa-trash', 'class': 'btn-danger'})
            rows.append({
                'cells': [
                    render_image_thumb(obj.image, obj.name, 'Ảnh chi nhánh'),
                    format_html('<div class="cell-title">{}</div><div class="cell-sub">ID: #{}</div>', obj.name, obj.pk),
                    format_html('<div>{}</div><div class="cell-sub">{}</div>', obj.address, obj.phone or '-'),
                    obj.opening_hours or '-',
                    format_html('<strong>{}</strong><div class="cell-sub">{} loại đang có hàng</div>', obj.medicine_total, obj.available_total),
                    status_badge,
                ],
                'actions': actions,
            })
        return queryset, columns, rows, filter_options, summary_cards, keyword

    if model_key == 'medicine':
        queryset = Medicine.objects.select_related('pharmacy')
        if keyword:
            queryset = queryset.filter(build_search_query(keyword, ADMIN_MODELS[model_key]['search_fields']))

        pharmacy_id = request.GET.get('pharmacy', '')
        if pharmacy_id:
            queryset = queryset.filter(pharmacy_id=pharmacy_id)

        stock = request.GET.get('stock', '')
        if stock == 'in':
            queryset = queryset.filter(quantity__gt=LOW_STOCK_THRESHOLD)
        elif stock == 'low':
            queryset = queryset.filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD)
        elif stock == 'out':
            queryset = queryset.filter(quantity__lte=0)

        rx = request.GET.get('rx', '')
        if rx == 'yes':
            queryset = queryset.filter(prescription_required=True)
        elif rx == 'no':
            queryset = queryset.filter(prescription_required=False)

        queryset = apply_admin_sort(queryset, model_key, request.GET.get('sort', 'newest'))
        columns = ['Ảnh', 'Sản phẩm', 'Chi nhánh', 'Giá bán', 'Tồn kho', 'Kê đơn']
        summary_cards = [
            {'label': 'Tổng sản phẩm', 'value': Medicine.objects.count(), 'tone': 'primary'},
            {'label': 'Sắp hết hàng', 'value': Medicine.objects.filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD).count(), 'tone': 'warning'},
            {'label': 'Hết hàng', 'value': Medicine.objects.filter(quantity__lte=0).count(), 'tone': 'danger'},
            {'label': 'Cần kê đơn', 'value': Medicine.objects.filter(prescription_required=True).count(), 'tone': 'info'},
        ]
        filter_options = get_medicine_filter_options(request)

        rows = []
        for obj in queryset:
            actions = [
                {'url': reverse('custom_admin_update', kwargs={'model_key': 'medicine', 'pk': obj.pk}), 'label': 'Cập nhật', 'icon': 'fas fa-pen', 'class': 'btn-primary'},
            ]
            if can_delete_object(request.user, model_key, obj):
                actions.append({'url': reverse('custom_admin_delete', kwargs={'model_key': 'medicine', 'pk': obj.pk}), 'label': 'Xóa', 'icon': 'fas fa-trash', 'class': 'btn-danger'})
            rows.append({
                'cells': [
                    render_image_thumb(obj.image, obj.name, 'Ảnh sản phẩm'),
                    format_html(
                        '<div class="cell-title">{}</div><div class="cell-sub">{} • {}</div>',
                        obj.name,
                        obj.category or 'Chưa phân loại',
                        obj.unit or '-',
                    ),
                    obj.pharmacy.name if obj.pharmacy else '-',
                    format_money(obj.price),
                    format_html('<div>{}</div><div class="mt-1">{}</div>', obj.quantity, render_stock_badge(obj.quantity)),
                    render_prescription_badge(obj.prescription_required),
                ],
                'actions': actions,
            })
        return queryset, columns, rows, filter_options, summary_cards, keyword

    if model_key == 'order':
        queryset = Order.objects.select_related('pharmacy', 'user').annotate(item_total=Count('items'))
        if keyword:
            queryset = queryset.filter(build_search_query(keyword, ADMIN_MODELS[model_key]['search_fields']))

        status = request.GET.get('status', '')
        if status:
            queryset = queryset.filter(status=status)

        pharmacy_id = request.GET.get('pharmacy', '')
        if pharmacy_id:
            queryset = queryset.filter(pharmacy_id=pharmacy_id)

        queryset = apply_admin_sort(queryset, model_key, request.GET.get('sort', 'newest'))
        columns = ['Mã đơn', 'Khách hàng', 'Chi nhánh xử lý', 'Tổng tiền', 'Trạng thái']
        summary_cards = [
            {'label': 'Đơn chờ xử lý', 'value': Order.objects.filter(status=Order.STATUS_PENDING).count(), 'tone': 'warning'},
            {'label': 'Đang giao', 'value': Order.objects.filter(status=Order.STATUS_SHIPPING).count(), 'tone': 'info'},
            {'label': 'Hoàn thành', 'value': Order.objects.filter(status=Order.STATUS_COMPLETED).count(), 'tone': 'success'},
            {'label': 'Đã hủy', 'value': Order.objects.filter(status=Order.STATUS_CANCELLED).count(), 'tone': 'danger'},
        ]
        filter_options = get_order_filter_options(request)

        rows = []
        for obj in queryset:
            rows.append({
                'cells': [
                    format_html(
                        '<div class="cell-title">#{}</div><div class="cell-sub">{} • {} sản phẩm</div>',
                        obj.pk,
                        obj.created_at.strftime('%d/%m/%Y %H:%M'),
                        obj.item_total,
                    ),
                    format_html('<div>{}</div><div class="cell-sub">{}</div>', obj.full_name, obj.phone),
                    obj.pharmacy.name if obj.pharmacy else render_badge('Chưa gán', 'secondary'),
                    format_money(obj.final_total_price),
                    render_order_status_badge(obj.status),
                ],
                'actions': ([
                    {'url': reverse('custom_admin_order_detail', kwargs={'pk': obj.pk}), 'label': 'Xem chi tiết', 'icon': 'fas fa-eye', 'class': 'btn-info'},
                ] + ([
                    {'url': reverse('custom_admin_delete', kwargs={'model_key': 'order', 'pk': obj.pk}), 'label': 'Xóa', 'icon': 'fas fa-trash', 'class': 'btn-danger'},
                ] if can_delete_object(request.user, 'order', obj) else [])),
            })
        return queryset, columns, rows, filter_options, summary_cards, keyword

    queryset = User.objects.all()
    if keyword:
        queryset = queryset.filter(build_search_query(keyword, ADMIN_MODELS[model_key]['search_fields']))

    role = request.GET.get('role', '')
    if role == 'customer':
        queryset = queryset.filter(is_staff=False, is_superuser=False)
    elif role == 'staff':
        queryset = queryset.filter(is_staff=True, is_superuser=False)
    elif role == 'superuser':
        queryset = queryset.filter(is_superuser=True)

    active = request.GET.get('active', '')
    if active == 'yes':
        queryset = queryset.filter(is_active=True)
    elif active == 'no':
        queryset = queryset.filter(is_active=False)

    queryset = apply_admin_sort(queryset, model_key, request.GET.get('sort', 'newest'))
    columns = ['Tài khoản', 'Thông tin liên hệ', 'Vai trò', 'Trạng thái']
    summary_cards = [
        {'label': 'Tổng tài khoản', 'value': User.objects.count(), 'tone': 'primary'},
        {'label': 'Nhân viên', 'value': User.objects.filter(is_staff=True, is_superuser=False).count(), 'tone': 'info'},
        {'label': 'Khách hàng', 'value': User.objects.filter(is_staff=False, is_superuser=False).count(), 'tone': 'secondary'},
        {'label': 'Bị khóa', 'value': User.objects.filter(is_active=False).count(), 'tone': 'danger'},
    ]
    filter_options = get_user_filter_options(request)

    rows = []
    for obj in queryset:
        actions = []
        if not obj.is_superuser or request.user.is_superuser:
            actions.append({'url': reverse('custom_admin_update', kwargs={'model_key': 'user', 'pk': obj.pk}), 'label': 'Cập nhật', 'icon': 'fas fa-pen', 'class': 'btn-primary'})
        if can_delete_object(request.user, model_key, obj):
            actions.append({'url': reverse('custom_admin_delete', kwargs={'model_key': 'user', 'pk': obj.pk}), 'label': 'Xóa', 'icon': 'fas fa-trash', 'class': 'btn-danger'})
        rows.append({
            'cells': [
                format_html('<div class="cell-title">{}</div><div class="cell-sub">ID: #{}</div>', obj.username, obj.pk),
                format_html('<div>{}</div><div class="cell-sub">{} {}</div>', obj.email or '-', obj.last_name or '', obj.first_name or ''),
                render_user_role_badge(obj),
                render_badge('Đang hoạt động', 'success') if obj.is_active else render_badge('Đã khóa', 'danger'),
            ],
            'actions': actions,
        })
    return queryset, columns, rows, filter_options, summary_cards, keyword


@user_passes_test(staff_check, login_url='login')
def custom_admin_dashboard(request):
    recent_orders_queryset = Order.objects.select_related('pharmacy').order_by('-created_at', '-id')
    low_stock_queryset = Medicine.objects.select_related('pharmacy').filter(
        quantity__gt=0,
        quantity__lte=LOW_STOCK_THRESHOLD,
    ).order_by('quantity', 'name')
    branch_overview_queryset = Pharmacy.objects.annotate(
        medicine_total=Count('medicines', distinct=True),
        available_total=Count('medicines', filter=Q(medicines__quantity__gt=0), distinct=True),
    ).order_by('-available_total', 'name')

    recent_orders_page_obj = Paginator(recent_orders_queryset, ADMIN_PAGE_SIZE).get_page(
        request.GET.get('orders_page')
    )
    low_stock_page_obj = Paginator(low_stock_queryset, 3).get_page(
        request.GET.get('stock_page')
    )
    branch_overview_page_obj = Paginator(branch_overview_queryset, ADMIN_PAGE_SIZE).get_page(
        request.GET.get('branch_page')
    )

    context = {
        'page_title': 'Dashboard quản trị hệ thống',
        'current_model': 'dashboard',
        'pharmacy_count': Pharmacy.objects.count(),
        'medicine_count': Medicine.objects.count(),
        'pending_order_count': Order.objects.filter(status=Order.STATUS_PENDING).count(),
        'shipping_order_count': Order.objects.filter(status=Order.STATUS_SHIPPING).count(),
        'low_stock_count': Medicine.objects.filter(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD).count(),
        'out_of_stock_count': Medicine.objects.filter(quantity__lte=0).count(),
        'recent_orders': recent_orders_page_obj.object_list,
        'recent_orders_page_obj': recent_orders_page_obj,
        'low_stock_medicines': low_stock_page_obj.object_list,
        'low_stock_page_obj': low_stock_page_obj,
        'branch_overview': branch_overview_page_obj.object_list,
        'branch_overview_page_obj': branch_overview_page_obj,
        'can_manage_pharmacy': can_access_admin_model(request.user, 'pharmacy'),
        'can_manage_medicine': can_access_admin_model(request.user, 'medicine'),
        'can_manage_order': can_access_admin_model(request.user, 'order'),
        'can_manage_user': can_access_admin_model(request.user, 'user'),
        'can_create_pharmacy': request.user.is_superuser,
        'can_create_medicine': request.user.is_staff,
        'can_create_user': request.user.is_superuser,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@user_passes_test(staff_check, login_url='login')
def custom_admin_list(request, model_key):
    denied_response = require_admin_model_access(request, model_key)
    if denied_response:
        return denied_response

    config = get_admin_config(model_key)
    queryset, columns, rows, filter_options, summary_cards, keyword = build_list_data(model_key, request)

    paginator = Paginator(queryset, ADMIN_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_rows = rows[(page_obj.start_index() - 1):page_obj.end_index()] if page_obj.paginator.count else []

    create_allowed = (
        model_key in {'pharmacy', 'medicine', 'user'}
        and (
            request.user.is_superuser
            or (request.user.is_staff and not request.user.is_superuser and model_key == 'medicine')
        )
    )
    create_label = {
        'pharmacy': 'Thêm chi nhánh',
        'medicine': 'Thêm sản phẩm thuốc',
        'user': 'Thêm tài khoản',
    }.get(model_key, '')

    context = {
        'page_title': f'Quản lý {config["title_plural"]}',
        'title': config['title_plural'],
        'model_key': model_key,
        'current_model': model_key,
        'columns': columns,
        'rows': page_rows,
        'page_obj': page_obj,
        'keyword': keyword,
        'filter_options': filter_options,
        'summary_cards': summary_cards,
        'create_allowed': create_allowed,
        'create_label': create_label,
    }
    return render(request, 'admin_panel/list.html', context)


@user_passes_test(staff_check, login_url='login')
def custom_admin_create(request, model_key):
    denied_response = require_admin_model_access(request, model_key)
    if denied_response:
        return denied_response

    if model_key not in {'pharmacy', 'medicine', 'user'}:
        raise Http404('Không tìm thấy trang thêm dữ liệu')

    config = get_admin_config(model_key)
    form_class = config['form_create']

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, admin_user=request.user)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Đã thêm {config['title'].lower()} '{get_object_label(obj)}' thành công.")
            return redirect('custom_admin_list', model_key=model_key)
    else:
        form = form_class(admin_user=request.user)

    context = {
        'page_title': f'Thêm {config["title"]}',
        'title': config['title'],
        'model_key': model_key,
        'current_model': model_key,
        'form': form,
        'form_sections': get_admin_form_sections(form, model_key),
        'is_create': True,
        'object': None,
    }
    return render(request, 'admin_panel/form.html', context)


@user_passes_test(staff_check, login_url='login')
def custom_admin_update(request, model_key, pk):
    denied_response = require_admin_model_access(request, model_key)
    if denied_response:
        return denied_response

    if model_key == 'order':
        return redirect('custom_admin_order_detail', pk=pk)

    config = get_admin_config(model_key)
    model = config['model']
    obj = get_object_or_404(model, pk=pk)

    if model_key == 'user' and obj.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Bạn không có quyền chỉnh sửa tài khoản superuser.')
        return redirect('custom_admin_list', model_key=model_key)

    form_class = config['form_update']

    if request.method == 'POST':
        post_data = request.POST.copy()
        if request.POST.get('delete_image_action') == '1' and 'delete_image' in form_class(instance=obj, admin_user=request.user).fields:
            post_data['delete_image'] = 'on'
        form = form_class(post_data, request.FILES, instance=obj, admin_user=request.user)
        if form.is_valid():
            updated_obj = form.save()
            messages.success(request, f"Đã cập nhật {config['title'].lower()} '{get_object_label(updated_obj)}'.")
            return redirect('custom_admin_list', model_key=model_key)
    else:
        form = form_class(instance=obj, admin_user=request.user)

    context = {
        'page_title': f'Cập nhật {config["title"]}',
        'title': config['title'],
        'model_key': model_key,
        'current_model': model_key,
        'form': form,
        'form_sections': get_admin_form_sections(form, model_key),
        'object': obj,
        'is_create': False,
    }
    return render(request, 'admin_panel/form.html', context)


@user_passes_test(staff_check, login_url='login')
def custom_admin_order_detail(request, pk):
    denied_response = require_admin_model_access(request, 'order')
    if denied_response:
        return denied_response

    order = get_object_or_404(
        Order.objects.select_related('pharmacy', 'user').prefetch_related('items__medicine'),
        pk=pk,
    )

    if request.method == 'POST':
        form = OrderStatusUpdateForm(request.POST, instance=order, admin_user=request.user)
        if form.is_valid():
            previous_status = order.status
            try:
                with transaction.atomic():
                    updated_order = form.save(commit=False)
                    updated_order.save()
                    if previous_status != updated_order.status and updated_order.status == Order.STATUS_CANCELLED:
                        transaction.on_commit(
                            lambda cancelled_order=updated_order, current_request=request: send_order_cancelled_email(
                                cancelled_order,
                                request=current_request,
                            )
                        )
                messages.success(request, f'Đã cập nhật đơn hàng #{order.pk}.')
                return redirect('custom_admin_order_detail', pk=order.pk)
            except ValueError as exc:
                form.add_error(None, str(exc))
    else:
        form = OrderStatusUpdateForm(instance=order, admin_user=request.user)

    context = {
        'page_title': f'Chi tiết đơn hàng #{order.pk}',
        'current_model': 'order',
        'order': order,
        'update_form': form,
        'order_items': order.items.all(),
        'can_delete_order': can_delete_object(request.user, 'order', order),
    }
    return render(request, 'admin_panel/order_detail.html', context)


@user_passes_test(staff_check, login_url='login')
def custom_admin_delete(request, model_key, pk):
    denied_response = require_admin_model_access(request, model_key)
    if denied_response:
        return denied_response

    config = get_admin_config(model_key)
    model = config['model']
    obj = get_object_or_404(model, pk=pk)

    if not can_delete_object(request.user, model_key, obj):
        messages.error(request, 'Bạn không có quyền xóa dữ liệu này.')
        return redirect('custom_admin_list', model_key=model_key)

    if request.method == 'POST':
        object_name = get_object_label(obj)
        obj.delete()
        messages.success(request, f"Đã xóa {config['title'].lower()} '{object_name}'.")
        return redirect('custom_admin_list', model_key=model_key)

    context = {
        'page_title': f'Xóa {config["title"]}',
        'title': config['title'],
        'model_key': model_key,
        'current_model': model_key,
        'object': obj,
        'object_name': get_object_label(obj),
    }
    return render(request, 'admin_panel/delete.html', context)




def custom_404_view(request, exception=None):
    return render(
        request,
        'errors/404.html',
        {
            'requested_path': request.get_full_path(),
        },
        status=404,
    )
