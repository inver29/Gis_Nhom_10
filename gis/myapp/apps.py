from django.apps import AppConfig

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'
    # [THAY ĐỔI] Đổi tên hiển thị của App trên menu
    verbose_name = "QUẢN LÝ NGHIỆP VỤ"