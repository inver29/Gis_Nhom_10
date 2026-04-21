"""
Django settings for gis project.
"""

import os
from pathlib import Path

try:
    import jazzmin  # noqa: F401
except ImportError:
    JAZZMIN_INSTALLED = False
else:
    JAZZMIN_INSTALLED = True

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-dk3ssefefhbfbzdndrh@)@y%&jyh#_(fuxj-d*e9!@02kqu4%^wmhe%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp',
]

if JAZZMIN_INSTALLED:
    INSTALLED_APPS.insert(0, 'jazzmin')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'myapp.middleware.FriendlyNotFoundMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gis.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Prefer this project's templates over third-party app templates
        # so custom auth/recovery pages are not shadowed by Jazzmin defaults.
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'myapp' / 'templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'myapp.context_processors.site_chrome',
            ],
        },
    },
]

WSGI_APPLICATION = 'gis.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'gis_db',
        'USER': 'postgres',
        'PASSWORD': '12345',  # Mật khẩu của bạn
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT_DIR', BASE_DIR.parent / 'gis_media'))

DEFAULT_FILE_STORAGE = 'myapp.storage.DatabaseMediaStorage'
STORAGES = {
    'default': {'BACKEND': 'myapp.storage.DatabaseMediaStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
DB_MEDIA_URL = '/db-media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_NAME = os.getenv('SITE_NAME', 'GIS Pharma')
SITE_SUPPORT_EMAIL = os.getenv('SITE_SUPPORT_EMAIL', 'support@gispharma.local')
SITE_BASE_URL = os.getenv('SITE_BASE_URL', 'http://127.0.0.1:8000')

MAILTRAP_HOST = os.getenv('MAILTRAP_HOST', 'sandbox.smtp.mailtrap.io')
MAILTRAP_PORT = int(os.getenv('MAILTRAP_PORT', '587'))
MAILTRAP_USERNAME = os.getenv('MAILTRAP_USERNAME', os.getenv('EMAIL_HOST_USER', 'fe43f21885cccd'))
MAILTRAP_PASSWORD = os.getenv('MAILTRAP_PASSWORD', os.getenv('EMAIL_HOST_PASSWORD', 'f003d051485341'))
MAILTRAP_USE_TLS = os.getenv('MAILTRAP_USE_TLS', 'true').lower() in {'1', 'true', 'yes'}

if MAILTRAP_USERNAME and MAILTRAP_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

EMAIL_HOST = MAILTRAP_HOST
EMAIL_PORT = MAILTRAP_PORT
EMAIL_HOST_USER = MAILTRAP_USERNAME
EMAIL_HOST_PASSWORD = MAILTRAP_PASSWORD
EMAIL_USE_TLS = MAILTRAP_USE_TLS
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'GIS Pharma <no-reply@gispharma.local>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
PASSWORD_RESET_TIMEOUT = 60 * 60

PAYMENT_BANK_QR_IMAGE_URL = os.getenv('PAYMENT_BANK_QR_IMAGE_URL', '').strip()
PAYMENT_MOMO_QR_IMAGE_URL = os.getenv('PAYMENT_MOMO_QR_IMAGE_URL', '').strip()

# --- CẤU HÌNH GIAO DIỆN ADMIN (JAZZMIN) TỐI GIẢN ---
JAZZMIN_SETTINGS = {
    # Tiêu đề & Logo
    "site_title": "Quản lý Nhà thuốc",
    "site_header": "Hệ thống Dược",
    "site_brand": "GIS Pharma",
    "welcome_sign": "Xin chào, chúc bạn một ngày làm việc hiệu quả!",
    "copyright": "GIS Team",
    
    # Tìm kiếm nhanh Đơn hàng (quan trọng nhất)
    "search_model": "myapp.Order",

    # Menu trên cùng (Top Menu) - Giữ đơn giản
    "topmenu_links": [
        {"name": "Về trang bán hàng", "url": "home", "permissions": ["auth.view_user"]},
        {"name": "Xem Bản đồ GIS", "url": "map_view", "new_window": True},
    ],

    # Menu bên trái (Sidebar)
    "show_sidebar": True,
    "navigation_expanded": True,
    
    # Ẩn các model kỹ thuật rườm rà (Giúp giao diện sạch hơn)
    "hide_models": [
        "myapp.Cart",           # Ẩn giỏ hàng (không cần quản lý ở đây)
        "myapp.CartItem",       # Ẩn chi tiết giỏ
        "myapp.OrderItem",      # Ẩn chi tiết đơn (đã hiện trong Đơn hàng rồi)
    ],

    # Sắp xếp thứ tự ưu tiên (Cái gì dùng nhiều đưa lên đầu)
    "order_with_respect_to": [
        "myapp.Order",          # 1. Đơn hàng (Quan trọng nhất)
        "myapp.Medicine",       # 2. Thuốc
        "myapp.Pharmacy",       # 3. Chi nhánh
        "auth.User"             # 5. Tài khoản
    ],

    # Icon đẹp mắt, dễ nhìn
    "icons": {
        "auth": "fas fa-cogs",
        "auth.user": "fas fa-user-shield",
        "myapp.Pharmacy": "fas fa-hospital",
        "myapp.Medicine": "fas fa-capsules",
        "myapp.Order": "fas fa-file-invoice-dollar",
        "myapp.UserProfile": "fas fa-id-badge",
    },
    "custom_css": "css/admin-jazzmin.css",
    "use_google_fonts_cdn": True,
    "show_ui_builder": False, # Tắt nút chỉnh sửa giao diện thừa thãi
}

# --- TÙY CHỈNH MÀU SẮC (SẠCH & SÁNG) ---
JAZZMIN_UI_TWEAKS = {
    "theme": "spacelab",  # Theme màu trắng/xám nhẹ, rất chuyên nghiệp
    #"theme": "flatly",   # Hoặc dùng flatly nếu thích màu xanh lá chủ đạo
    
    "navbar": "navbar-light navbar-white", # Thanh trên cùng màu trắng
    "sidebar": "sidebar-light-primary",    # Menu trái màu sáng (thay vì đen sì)
    "accent": "accent-primary",            # Màu nhấn xanh dương
}

CSRF_FAILURE_VIEW = 'myapp.views.custom_csrf_failure_view'
