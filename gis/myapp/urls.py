from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('map/', views.map_view, name='map_view'),
    path('products/', views.product_list, name='product_list'),
    path('order/', views.order_create, name='order_create'),

    # URL đã được sửa thành 'pharmacy' cho đúng chủ đề
    path('pharmacy/<int:pharmacy_id>/', views.pharmacy_detail, name='pharmacy_detail'),

    path('api/route/', views.get_route_api, name='api_route'),
    path('api/nearby/', views.get_nearby_api, name='api_nearby'),
]
