"""
Django settings for gis project.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-dk3ssefefhbfbzdndrh@)@y%&jyh#_(fuxj-d*e9!@02kqu4%^wmhe%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gis.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
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
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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
        "myapp.StaffProfile": "fas fa-id-badge",
    },
    
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