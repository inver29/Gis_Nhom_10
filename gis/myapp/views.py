from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse

from .models import Pharmacy, Branch, Medicine, Order
from .tool import RoutingTool, calc_shipping_fee, filter_pharmacies_in_radius


def home(request):
    return render(request, 'home.html')


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

    return render(request, 'map.html', {
        'pharmacies': pharmacy_list
    })


def pharmacy_detail(request, pharmacy_id):
    pharmacy = get_object_or_404(Pharmacy, pk=pharmacy_id)
    medicines = Medicine.objects.filter(pharmacy=pharmacy)
    return render(request, 'pharmacy_detail.html', {
        'pharmacy': pharmacy,
        'medicines': medicines
    })


def get_route_api(request):
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')
    
    # Lấy mode và thời gian
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
                # Tính phí ship theo Mode
                fee_value, fee_text = calc_shipping_fee(dist, mode)
                
                route['shipping_fee'] = fee_text
                route['shipping_fee_value'] = fee_value

        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_nearby_api(request):
    user_lat = request.GET.get('user_lat')
    user_lng = request.GET.get('user_lng')
    radius_km = request.GET.get('radius_km', 0)

    if not all([user_lat, user_lng]):
        return JsonResponse({'error': 'Thiếu tọa độ người dùng'}, status=400)

    pharmacies_db = Pharmacy.objects.filter(has_stock=True)
    filtered = filter_pharmacies_in_radius(pharmacies_db, user_lat, user_lng, radius_km)

    return JsonResponse({
        'user': {
            'lat': float(user_lat),
            'lng': float(user_lng),
            'radius_km': float(radius_km or 0)
        },
        'items': filtered
    })


def product_list(request):
    medicines = Medicine.objects.select_related('pharmacy')
    return render(request, 'products.html', {
        'medicines': medicines
    })


def order_create(request):
    pharmacy_id = request.GET.get('pharmacy_id')
    distance = float(request.GET.get('distance', 0))
    shipping_fee = int(request.GET.get('shipping_fee', 0))

    pharmacy = None
    medicines = Medicine.objects.none()

    if pharmacy_id:
        pharmacy = get_object_or_404(Pharmacy, id=pharmacy_id)
        medicines = pharmacy.medicines.all()

    if request.method == 'POST':
        medicine_id = request.POST.get('medicine')
        quantity = int(request.POST.get('quantity'))
        shipping_fee = int(request.POST.get('shipping_fee', 0))

        medicine = get_object_or_404(Medicine, id=medicine_id)

        if quantity > medicine.quantity:
            return render(request, 'order.html', {
                'pharmacy': pharmacy,
                'medicines': medicines,
                'distance': distance,
                'shipping_fee': shipping_fee,
                'error': 'Số lượng vượt quá tồn kho'
            })

        total_price = medicine.price * quantity + shipping_fee

        Order.objects.create(
            pharmacy=pharmacy,
            medicine=medicine,
            quantity=quantity,
            total_price=total_price
        )

        medicine.quantity -= quantity
        medicine.save()

        return redirect('home')

    return render(request, 'order.html', {
        'pharmacy': pharmacy,
        'medicines': medicines,
        'distance': distance,
        'shipping_fee': shipping_fee
    })