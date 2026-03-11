from django.urls import path

from . import views

urlpatterns = [
    # Trang chính
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('map/', views.map_view, name='map_view'),

    # Giỏ hàng
    path('cart/', views.cart_detail, name='cart_detail'),
    path('add-to-cart/<int:medicine_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-item/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),

    # Thanh toán
    path('checkout/', views.checkout, name='checkout'),

    # Tài khoản
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('history/', views.order_history, name='order_history'),

    # Chi tiết nhà thuốc
    path('pharmacy/<int:pharmacy_id>/', views.pharmacy_detail, name='pharmacy_detail'),

    # API GIS
    path('api/route/', views.get_route_api, name='api_route'),
    path('api/nearest-pharmacy/', views.find_best_pharmacy_api, name='api_nearest_pharmacy'),
]