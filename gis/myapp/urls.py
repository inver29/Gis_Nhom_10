from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:medicine_id>/', views.medicine_detail, name='medicine_detail'),
    path('map/', views.map_view, name='map_view'),

    path('cart/', views.cart_detail, name='cart_detail'),
    path('add-to-cart/<int:medicine_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-item/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),

    path('checkout/', views.checkout, name='checkout'),
    path('order/', views.checkout, name='order_create'),

    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.txt',
            subject_template_name='registration/password_reset_subject.txt',
            html_email_template_name='registration/password_reset_email.html',
            success_url='/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('account/', views.account_view, name='account'),
    path('history/', views.order_history, name='order_history'),

    path('pharmacy/<int:pharmacy_id>/', views.pharmacy_detail, name='pharmacy_detail'),

    path('api/route/', views.get_route_api, name='api_route'),
    path('api/find-best-pharmacy/', views.find_best_pharmacy_api_v2, name='find_best_pharmacy_api'),
    path('api/nearest-pharmacy/', views.find_best_pharmacy_api_v2, name='nearest_pharmacy_api'),
    path('api/catalog-search/', views.catalog_search_api, name='catalog_search_api'),
    path('api/pharmacies-nearby/', views.nearby_pharmacies_api, name='nearby_pharmacies_api'),
    path('api/search-address/', views.search_address_api, name='search_address_api'),
    path('api/reverse-address/', views.reverse_address_api, name='reverse_address_api'),
    path('api/save-profile-address/', views.save_profile_address_api, name='save_profile_address_api'),

    path('admin/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('admin/order/<int:pk>/', views.custom_admin_order_detail, name='custom_admin_order_detail'),
    path('admin/<str:model_key>/', views.custom_admin_list, name='custom_admin_list'),
    path('admin/<str:model_key>/create/', views.custom_admin_create, name='custom_admin_create'),
    path('admin/<str:model_key>/<int:pk>/edit/', views.custom_admin_update, name='custom_admin_update'),
    path('admin/<str:model_key>/<int:pk>/delete/', views.custom_admin_delete, name='custom_admin_delete'),
]
