from django.contrib.auth.models import User
from django.db import models
from django.db.models import Avg
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify
from uuid import uuid4

from .model_helpers import (
    MEDICINE_SHARED_SYNC_FIELDS,
    build_gallery_urls,
    build_gallery_urls_from_text,
    build_medicine_catalog_key,
    encode_public_url,
    fold_text_for_match,
    get_medicine_catalog_key_for_instance,
    get_medicine_image_name,
    normalize_gallery_url,
    resolve_media_url,
    sync_medicine_catalog_metadata,
)
from .storage import build_db_media_url


MEDICINE_PRODUCT_TYPE_MEDICINE = "medicine"
MEDICINE_PRODUCT_TYPE_SUPPLEMENT = "supplement"
MEDICINE_PRODUCT_TYPE_CHOICES = (
    (MEDICINE_PRODUCT_TYPE_MEDICINE, "Thuốc"),
    (MEDICINE_PRODUCT_TYPE_SUPPLEMENT, "Thực phẩm chức năng"),
)


class AboutPageContent(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    page_title = models.CharField(max_length=160, default="Giới thiệu GIS Pharma", verbose_name="Tiêu đề tab")

    hero_kicker = models.CharField(max_length=120, default="About GIS Pharma", verbose_name="Nhãn hero")
    hero_title = models.CharField(
        max_length=255,
        default="Giúp người dùng tìm đúng nhà thuốc, đúng sản phẩm và đúng chi nhánh nhanh hơn.",
        verbose_name="Tiêu đề hero",
    )
    hero_intro = models.TextField(
        default=(
            "GIS Pharma là website quản lý chuỗi nhà thuốc kết hợp bản đồ GIS, trưng bày sản phẩm và hỗ trợ đặt hàng trực tuyến. "
            "Trang giới thiệu mới được dàn lại theo hướng kể chuyện rõ hơn: vì sao hệ thống được xây dựng, người dùng đang cần gì, "
            "website giải quyết bằng cách nào và dữ liệu thật của hệ thống đang được trình bày ra sao."
        ),
        verbose_name="Mô tả hero",
    )
    hero_chip_1 = models.CharField(max_length=120, default="Tra cứu theo danh mục", verbose_name="Chip hero 1")
    hero_chip_2 = models.CharField(max_length=120, default="Xem chi nhánh trên bản đồ", verbose_name="Chip hero 2")
    hero_chip_3 = models.CharField(max_length=120, default="Theo dõi đơn hàng tập trung", verbose_name="Chip hero 3")
    hero_primary_label = models.CharField(max_length=80, default="Xem sản phẩm", verbose_name="Nút hero chính")
    hero_secondary_label = models.CharField(max_length=80, default="Mở bản đồ", verbose_name="Nút hero phụ")
    visual_title = models.CharField(
        max_length=180,
        default="Trang giới thiệu được dựng lại theo kiểu story + value + CTA",
        verbose_name="Tiêu đề thẻ visual",
    )
    visual_description = models.TextField(
        default="Tập trung vào câu chuyện, lợi ích thật cho người dùng, vai trò của dữ liệu GIS và phần trình bày chi nhánh thay vì chỉ là một trang mô tả tĩnh.",
        verbose_name="Mô tả thẻ visual",
    )
    pharmacy_stat_note = models.TextField(
        default="Dữ liệu địa điểm, giờ hoạt động và hình ảnh được đưa thẳng vào trải nghiệm tra cứu.",
        verbose_name="Ghi chú thống kê chi nhánh",
    )
    pharmacy_stat_label = models.CharField(max_length=120, default="chi nhánh đang hiển thị", verbose_name="Nhãn nổi chi nhánh")
    medicine_stat_note = models.TextField(
        default="Catalog thuốc và thực phẩm chức năng được tổ chức rõ ràng hơn cho người dùng.",
        verbose_name="Ghi chú thống kê sản phẩm",
    )
    medicine_stat_label = models.CharField(max_length=120, default="sản phẩm trên hệ thống", verbose_name="Nhãn nổi sản phẩm")
    stat_pharmacy_label = models.CharField(max_length=180, default="Chi nhánh đang được quản lý và giới thiệu trên website.", verbose_name="Mô tả ô thống kê chi nhánh")
    stat_medicine_label = models.CharField(max_length=180, default="Sản phẩm dược phẩm và chăm sóc sức khỏe đang hiển thị.", verbose_name="Mô tả ô thống kê sản phẩm")
    stat_order_label = models.CharField(max_length=180, default="Đơn hàng đã được hệ thống tiếp nhận và xử lý.", verbose_name="Mô tả ô thống kê đơn hàng")
    stat_review_label = models.CharField(max_length=180, default="Lượt đánh giá giúp tăng độ tin cậy cho sản phẩm và chi nhánh.", verbose_name="Mô tả ô thống kê đánh giá")

    story_tag = models.CharField(max_length=120, default="Câu chuyện", verbose_name="Nhãn khối câu chuyện")
    story_title = models.CharField(max_length=180, default="Tại sao GIS Pharma được xây dựng?", verbose_name="Tiêu đề câu chuyện")
    story_body = models.TextField(
        default="Người dùng thường gặp 3 khó khăn khi tìm nhà thuốc trực tuyến: không biết chi nhánh nào gần mình, không rõ nơi nào còn hàng và khó đánh giá nhanh chất lượng thông tin trước khi mua. GIS Pharma được xây dựng để gom các mảnh dữ liệu đó vào cùng một luồng trải nghiệm.",
        verbose_name="Nội dung câu chuyện",
    )
    story_item_1_title = models.CharField(max_length=160, default="Đưa dữ liệu bản đồ vào quyết định mua hàng", verbose_name="Câu chuyện - ý 1")
    story_item_1_body = models.TextField(default="Vị trí chi nhánh không đứng riêng mà trở thành một phần trực tiếp của hành trình chọn nơi mua.", verbose_name="Câu chuyện - mô tả ý 1")
    story_item_2_title = models.CharField(max_length=160, default="Chuẩn hóa dữ liệu sản phẩm theo catalog", verbose_name="Câu chuyện - ý 2")
    story_item_2_body = models.TextField(default="Tên, mô tả, hình ảnh và nhóm sản phẩm được giữ đồng nhất hơn giữa các chi nhánh.", verbose_name="Câu chuyện - mô tả ý 2")
    story_item_3_title = models.CharField(max_length=160, default="Tạo ra một hành trình liền mạch", verbose_name="Câu chuyện - ý 3")
    story_item_3_body = models.TextField(default="Từ giới thiệu, xem sản phẩm, xem bản đồ, thêm giỏ hàng đến theo dõi đơn đều đi trên cùng một hệ thống.", verbose_name="Câu chuyện - mô tả ý 3")

    problem_tag = models.CharField(max_length=120, default="Điều người dùng cần", verbose_name="Nhãn khối vấn đề")
    problem_title = models.CharField(max_length=180, default="3 vấn đề cốt lõi mà trang giới thiệu mới nhấn mạnh", verbose_name="Tiêu đề vấn đề")
    problem_body = models.TextField(
        default="Thiết kế lại lần này không chỉ làm đẹp hơn mà còn làm rõ hơn: website này để làm gì, có điểm gì khác biệt và tại sao người xem nên tiếp tục đi vào các trang sản phẩm hoặc bản đồ.",
        verbose_name="Nội dung vấn đề",
    )
    problem_item_1_title = models.CharField(max_length=160, default="Tìm đúng sản phẩm nhanh hơn", verbose_name="Vấn đề - ý 1")
    problem_item_1_body = models.TextField(default="Người dùng có thể bắt đầu từ danh mục, sản phẩm nổi bật hoặc trang giới thiệu rồi đi thẳng sang catalog.", verbose_name="Vấn đề - mô tả ý 1")
    problem_item_2_title = models.CharField(max_length=160, default="Hiểu website chỉ trong vài giây", verbose_name="Vấn đề - ý 2")
    problem_item_2_body = models.TextField(default="Story, value, số liệu và CTA được đặt thành các khối rõ ràng để nội dung dễ quét hơn.", verbose_name="Vấn đề - mô tả ý 2")
    problem_item_3_title = models.CharField(max_length=160, default="Thấy ngay vai trò của chi nhánh và GIS", verbose_name="Vấn đề - ý 3")
    problem_item_3_body = models.TextField(default="Phần bản đồ và quản lý chi nhánh được đẩy lên thành lợi thế nổi bật thay vì nằm mờ trong nội dung.", verbose_name="Vấn đề - mô tả ý 3")

    value_tag = models.CharField(max_length=120, default="Giá trị cốt lõi", verbose_name="Nhãn khối giá trị")
    value_title = models.CharField(max_length=180, default="Trang giới thiệu mới nói ít hơn nhưng chứng minh rõ hơn.", verbose_name="Tiêu đề giá trị")
    value_body = models.TextField(default="Cấu trúc được làm lại theo kiểu “story + problem + value + CTA” để trang About có vai trò bán niềm tin, không chỉ là một trang văn bản mô tả chung chung.", verbose_name="Nội dung giá trị")
    value_card_1_title = models.CharField(max_length=120, default="Rõ về hệ thống", verbose_name="Giá trị 1")
    value_card_1_body = models.TextField(default="Người xem hiểu ngay website dùng để làm gì, vì sao có phần bản đồ và vì sao quản lý chi nhánh là trọng tâm của dự án.", verbose_name="Mô tả giá trị 1")
    value_card_2_title = models.CharField(max_length=120, default="Rõ về sản phẩm", verbose_name="Giá trị 2")
    value_card_2_body = models.TextField(default="Danh mục thuốc và thực phẩm chức năng được trình bày như một catalog thống nhất, dễ tra cứu hơn cho người dùng.", verbose_name="Mô tả giá trị 2")
    value_card_3_title = models.CharField(max_length=120, default="Rõ về chi nhánh", verbose_name="Giá trị 3")
    value_card_3_body = models.TextField(default="Chi nhánh có vị trí, giờ mở cửa, hình ảnh và liên kết với bản đồ nên trải nghiệm tìm nơi mua trực quan hơn rõ rệt.", verbose_name="Mô tả giá trị 3")

    journey_tag = models.CharField(max_length=120, default="Hành trình dữ liệu", verbose_name="Nhãn hành trình")
    journey_title = models.CharField(max_length=180, default="Từ dữ liệu quản trị đến trải nghiệm phía người dùng.", verbose_name="Tiêu đề hành trình")
    journey_body = models.TextField(default="Phần giới thiệu mới mô tả rõ hơn vòng đời thông tin: nhập dữ liệu, chuẩn hóa catalog, hiển thị ngoài website và chuyển thành hành động mua hàng.", verbose_name="Nội dung hành trình")
    step_1_title = models.CharField(max_length=120, default="Chuẩn hóa sản phẩm", verbose_name="Bước 1")
    step_1_body = models.TextField(default="Tên, mô tả, hình ảnh và nhóm sản phẩm được gom lại theo catalog để dữ liệu gọn và đồng nhất hơn.", verbose_name="Mô tả bước 1")
    step_2_title = models.CharField(max_length=120, default="Gắn dữ liệu chi nhánh với bản đồ", verbose_name="Bước 2")
    step_2_body = models.TextField(default="Mỗi chi nhánh có địa chỉ, tọa độ và hình ảnh riêng để phần GIS đi vào trải nghiệm thật của website.", verbose_name="Mô tả bước 2")
    step_3_title = models.CharField(max_length=120, default="Ưu tiên nội dung dễ quét", verbose_name="Bước 3")
    step_3_body = models.TextField(default="Sản phẩm nổi bật, chi nhánh nổi bật và khuyến mãi được trình bày thành từng lớp thông tin rõ ràng hơn.", verbose_name="Mô tả bước 3")
    step_4_title = models.CharField(max_length=120, default="Chốt đơn trong cùng hệ thống", verbose_name="Bước 4")
    step_4_body = models.TextField(default="Từ xem thông tin đến thêm giỏ hàng, checkout, theo dõi đơn và đánh giá đều diễn ra trên một nền tảng.", verbose_name="Mô tả bước 4")

    product_tag = models.CharField(max_length=120, default="Danh mục sản phẩm", verbose_name="Nhãn sản phẩm")
    product_title = models.CharField(max_length=180, default="Website đang trưng bày những nhóm hàng nào?", verbose_name="Tiêu đề sản phẩm")
    product_body = models.TextField(default="Trang giới thiệu mới vẫn giữ dữ liệu thật của hệ thống để người xem hiểu website đang quản lý phạm vi nội dung nào.", verbose_name="Nội dung sản phẩm")
    medicine_summary_label = models.CharField(max_length=180, default="Sản phẩm thuộc nhóm thuốc đang được quản lý và hiển thị.", verbose_name="Nhãn thống kê thuốc")
    supplement_summary_label = models.CharField(max_length=180, default="Sản phẩm thuộc nhóm thực phẩm chức năng hiện có trên website.", verbose_name="Nhãn thống kê TPCN")
    category_empty_label = models.CharField(max_length=180, default="Danh mục sản phẩm đang được cập nhật.", verbose_name="Thông báo khi chưa có danh mục")

    branch_role_tag = models.CharField(max_length=120, default="Vai trò của chi nhánh", verbose_name="Nhãn vai trò chi nhánh")
    branch_role_title = models.CharField(max_length=180, default="Chi nhánh là trung tâm của trải nghiệm GIS Pharma", verbose_name="Tiêu đề vai trò chi nhánh")
    branch_role_body = models.TextField(default="Dự án này không chỉ là website bán hàng đơn lẻ. Nó là bài toán quản lý chuỗi chi nhánh, nên phần About cần làm rõ giá trị của từng điểm bán trong trải nghiệm tổng thể.", verbose_name="Nội dung vai trò chi nhánh")
    branch_role_item_1_title = models.CharField(max_length=160, default="Giờ hoạt động rõ ràng", verbose_name="Vai trò chi nhánh - ý 1")
    branch_role_item_1_body = models.TextField(default="Người dùng biết nhanh chi nhánh nào đang sẵn sàng phục vụ trước khi quyết định đi hoặc đặt mua.", verbose_name="Vai trò chi nhánh - mô tả ý 1")
    branch_role_item_2_title = models.CharField(max_length=160, default="Hình ảnh và mô tả riêng cho từng điểm bán", verbose_name="Vai trò chi nhánh - ý 2")
    branch_role_item_2_body = models.TextField(default="Mỗi chi nhánh có bản sắc riêng thay vì chỉ là một dòng địa chỉ khô khan.", verbose_name="Vai trò chi nhánh - mô tả ý 2")
    branch_role_item_3_title = models.CharField(max_length=160, default="Kết nối trực tiếp với bản đồ GIS", verbose_name="Vai trò chi nhánh - ý 3")
    branch_role_item_3_body = models.TextField(default="Vị trí, địa chỉ và hành động xem bản đồ được đưa vào cùng một luồng thao tác.", verbose_name="Vai trò chi nhánh - mô tả ý 3")

    branch_showcase_tag = models.CharField(max_length=120, default="Chi nhánh tiêu biểu", verbose_name="Nhãn chi nhánh tiêu biểu")
    branch_showcase_title = models.CharField(max_length=180, default="Một vài chi nhánh đang được giới thiệu trực tiếp trên website", verbose_name="Tiêu đề chi nhánh tiêu biểu")
    branch_showcase_body = models.TextField(default="Phần này giữ lại dữ liệu động của hệ thống nhưng trình bày theo kiểu showcase để trang About có cảm giác gần với một landing page hoàn chỉnh hơn.", verbose_name="Mô tả chi nhánh tiêu biểu")
    branch_showcase_badge = models.CharField(max_length=120, default="Điểm bán đang hoạt động", verbose_name="Nhãn trên thẻ chi nhánh")
    branch_showcase_map_note = models.CharField(max_length=180, default="Gắn trực tiếp với dữ liệu bản đồ và sản phẩm", verbose_name="Ghi chú bản đồ trên thẻ chi nhánh")
    branch_empty_tag = models.CharField(max_length=120, default="Đang cập nhật", verbose_name="Nhãn khi chưa có chi nhánh")
    branch_empty_title = models.CharField(max_length=180, default="Chi nhánh sẽ xuất hiện tại đây", verbose_name="Tiêu đề khi chưa có chi nhánh")
    branch_empty_body = models.TextField(default="Khi hệ thống có dữ liệu, phần giới thiệu sẽ tự động lấy chi nhánh để hiển thị trong khu showcase này.", verbose_name="Mô tả khi chưa có chi nhánh")

    cta_title = models.CharField(max_length=180, default="Sẵn sàng khám phá toàn bộ hệ thống GIS Pharma?", verbose_name="Tiêu đề CTA")
    cta_body = models.TextField(default="Bạn có thể đi tiếp theo 2 hướng ngay từ đây: xem toàn bộ catalog sản phẩm để trải nghiệm luồng mua hàng, hoặc mở bản đồ chi nhánh để kiểm tra cách website kết nối dữ liệu không gian vào trải nghiệm thực tế.", verbose_name="Nội dung CTA")
    cta_primary_label = models.CharField(max_length=80, default="Xem sản phẩm", verbose_name="Nút CTA chính")
    cta_secondary_label = models.CharField(max_length=80, default="Xem bản đồ", verbose_name="Nút CTA phụ")
    show_stats_section = models.BooleanField(default=True, verbose_name="Hiển thị khối thống kê")
    show_story_section = models.BooleanField(default=True, verbose_name="Hiển thị khối câu chuyện")
    show_value_section = models.BooleanField(default=True, verbose_name="Hiển thị khối giá trị nổi bật")
    show_journey_section = models.BooleanField(default=True, verbose_name="Hiển thị khối hành trình vận hành")
    show_branch_role_section = models.BooleanField(default=True, verbose_name="Hiển thị khối vai trò chi nhánh")
    show_branch_showcase_section = models.BooleanField(default=True, verbose_name="Hiển thị khối chi nhánh tiêu biểu")
    show_cta_section = models.BooleanField(default=True, verbose_name="Hiển thị khối lời kêu gọi hành động")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(singleton_key=1)
        if created and not AboutBuiltinSection.objects.filter(content=obj).exists():
            AboutBuiltinSection.objects.bulk_create(
                [
                    AboutBuiltinSection(
                        content=obj,
                        section_key=section_key,
                        sort_order=sort_order,
                    )
                    for section_key, sort_order in AboutBuiltinSection.default_blueprint()
                ]
            )
        return obj

    def __str__(self):
        return "Nội dung trang Giới thiệu"

    class Meta:
        verbose_name = "Nội dung trang Giới thiệu"
        verbose_name_plural = "Quản lý trang Giới thiệu"


class AboutPageSlide(models.Model):
    content = models.ForeignKey(
        AboutPageContent,
        on_delete=models.CASCADE,
        related_name="hero_slides",
        verbose_name="Nội dung trang Giới thiệu",
    )
    image = models.ImageField(upload_to="about/slides/", verbose_name="Ảnh slide", null=True, blank=True)
    legacy_static_path = models.CharField(max_length=255, blank=True, default="", verbose_name="Ảnh tĩnh dự phòng")
    alt_text = models.CharField(max_length=180, blank=True, default="", verbose_name="Mô tả ảnh")
    link_url = models.CharField(max_length=255, blank=True, default="", verbose_name="Liên kết khi bấm slide")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")

    def __str__(self):
        return self.alt_text or f"Slide giới thiệu #{self.pk or 'new'}"

    class Meta:
        verbose_name = "Slide trang Giới thiệu"
        verbose_name_plural = "Slider trang Giới thiệu"
        ordering = ["sort_order", "id"]


class AboutFeaturedBranchItem(models.Model):
    content = models.ForeignKey(
        AboutPageContent,
        on_delete=models.CASCADE,
        related_name="featured_branch_items",
        verbose_name="Nội dung trang Giới thiệu",
    )
    pharmacy = models.ForeignKey(
        "Pharmacy",
        on_delete=models.CASCADE,
        related_name="about_featured_entries",
        verbose_name="Chi nhánh lấy từ hệ thống",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180, verbose_name="Tên chi nhánh")
    summary = models.TextField(blank=True, default="", verbose_name="Mô tả ngắn")
    address = models.CharField(max_length=255, blank=True, default="", verbose_name="Địa chỉ hiển thị")
    hours = models.CharField(max_length=120, blank=True, default="", verbose_name="Giờ hoạt động")
    badge = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn nổi trên ảnh")
    map_note = models.CharField(max_length=180, blank=True, default="", verbose_name="Ghi chú phụ")
    icon_class = models.CharField(max_length=120, default="fas fa-clinic-medical", verbose_name="Lớp CSS biểu tượng")
    link_url = models.CharField(max_length=255, blank=True, default="", verbose_name="Liên kết khi bấm")
    link_label = models.CharField(max_length=80, blank=True, default="Xem chi nhánh", verbose_name="Nhãn nút liên kết")
    image = models.ImageField(upload_to="about/branches/", verbose_name="Ảnh chi nhánh", null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")

    def __str__(self):
        return self.title or f"Chi nhánh nổi bật #{self.pk or 'new'}"

    class Meta:
        verbose_name = "Chi nhánh tiêu biểu trang Giới thiệu"
        verbose_name_plural = "Chi nhánh tiêu biểu trang Giới thiệu"
        ordering = ["sort_order", "id"]


class AboutCustomBlock(models.Model):
    content = models.ForeignKey(
        AboutPageContent,
        on_delete=models.CASCADE,
        related_name="custom_blocks",
        verbose_name="Nội dung trang Giới thiệu",
    )
    kicker = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn khối")
    title = models.CharField(max_length=180, verbose_name="Tiêu đề khối")
    body = models.TextField(blank=True, default="", verbose_name="Nội dung khối")
    icon_class = models.CharField(max_length=120, default="fas fa-layer-group", verbose_name="Lớp CSS biểu tượng")
    link_label = models.CharField(max_length=80, blank=True, default="", verbose_name="Nhãn nút liên kết")
    link_url = models.CharField(max_length=255, blank=True, default="", verbose_name="Liên kết nút")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")

    def __str__(self):
        return self.title or f"Khối tùy chỉnh #{self.pk or 'new'}"

    class Meta:
        verbose_name = "Khối tùy chỉnh trang Giới thiệu"
        verbose_name_plural = "Khối tùy chỉnh trang Giới thiệu"
        ordering = ["sort_order", "id"]


class AboutBuiltinSection(models.Model):
    SECTION_STATS = "stats"
    SECTION_STORY = "story"
    SECTION_VALUE = "value"
    SECTION_JOURNEY = "journey"
    SECTION_BRANCH_ROLE = "branch_role"
    SECTION_BRANCH_SHOWCASE = "branch_showcase"
    SECTION_CTA = "cta"
    SECTION_CHOICES = (
        (SECTION_STATS, "Khối thống kê nhanh"),
        (SECTION_STORY, "Khối câu chuyện hệ thống"),
        (SECTION_VALUE, "Khối giá trị nổi bật"),
        (SECTION_JOURNEY, "Khối hành trình vận hành"),
        (SECTION_BRANCH_ROLE, "Khối vai trò chi nhánh"),
        (SECTION_BRANCH_SHOWCASE, "Khối chi nhánh tiêu biểu"),
        (SECTION_CTA, "Khối lời kêu gọi hành động"),
    )

    content = models.ForeignKey(
        AboutPageContent,
        on_delete=models.CASCADE,
        related_name="builtin_sections",
        verbose_name="Nội dung trang Giới thiệu",
    )
    section_key = models.CharField(max_length=40, choices=SECTION_CHOICES, verbose_name="Loại khối hệ thống")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")

    @classmethod
    def default_blueprint(cls):
        return [
            (cls.SECTION_STATS, 10),
            (cls.SECTION_STORY, 20),
            (cls.SECTION_VALUE, 30),
            (cls.SECTION_JOURNEY, 40),
            (cls.SECTION_BRANCH_ROLE, 50),
            (cls.SECTION_BRANCH_SHOWCASE, 60),
            (cls.SECTION_CTA, 70),
        ]

    def __str__(self):
        return dict(self.SECTION_CHOICES).get(self.section_key, self.section_key)

    class Meta:
        verbose_name = "Khối hệ thống trang Giới thiệu"
        verbose_name_plural = "Khối hệ thống trang Giới thiệu"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["content", "section_key"],
                name="uniq_about_builtin_section_per_page",
            )
        ]


class HomePageContent(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    hero_autoplay_interval = models.PositiveIntegerField(default=4000, verbose_name="Thời gian chuyển slide (ms)")
    category_section_kicker = models.CharField(max_length=120, default="Danh mục nổi bật", verbose_name="Nhãn khối danh mục")
    category_section_title = models.CharField(max_length=180, default="Tìm thuốc theo nhóm sản phẩm", verbose_name="Tiêu đề khối danh mục")
    category_section_link_label = models.CharField(max_length=80, default="Xem tất cả", verbose_name="Nhãn nút xem thêm danh mục")
    category_section_link_url = models.CharField(max_length=255, blank=True, default="/products/", verbose_name="Liên kết nút danh mục")
    commitment_section_kicker = models.CharField(max_length=120, default="Cam kết dịch vụ", verbose_name="Nhãn khối cam kết")
    commitment_section_title = models.CharField(max_length=180, default="Những giá trị chính của hệ thống", verbose_name="Tiêu đề khối cam kết")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(singleton_key=1)
        return obj

    def __str__(self):
        return "Nội dung trang chủ"

    class Meta:
        verbose_name = "Nội dung trang chủ"
        verbose_name_plural = "Quản lý trang chủ"


class HomeHeroSlide(models.Model):
    content = models.ForeignKey(
        HomePageContent,
        on_delete=models.CASCADE,
        related_name="hero_slides",
        verbose_name="Nội dung trang chủ",
    )
    image = models.ImageField(upload_to="home/slides/", verbose_name="Ảnh slide", null=True, blank=True)
    legacy_static_path = models.CharField(max_length=255, blank=True, default="", verbose_name="Ảnh tĩnh dự phòng")
    alt_text = models.CharField(max_length=180, blank=True, default="", verbose_name="Mô tả ảnh")
    link_url = models.CharField(max_length=255, blank=True, default="", verbose_name="Liên kết khi bấm slide")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")

    def __str__(self):
        return self.alt_text or f"Slide trang chủ #{self.pk or 'new'}"

    class Meta:
        verbose_name = "Slide trang chủ"
        verbose_name_plural = "Slider trang chủ"
        ordering = ["sort_order", "id"]


class HomeCategorySpotlightItem(models.Model):
    content = models.ForeignKey(
        HomePageContent,
        on_delete=models.CASCADE,
        related_name="category_spotlights",
        verbose_name="Nội dung trang chủ",
    )
    title = models.CharField(max_length=120, verbose_name="Tiêu đề thẻ")
    subtitle = models.CharField(max_length=120, blank=True, default="", verbose_name="Dòng phụ")
    icon_class = models.CharField(max_length=120, default="fas fa-capsules", verbose_name="Lớp CSS biểu tượng")
    link_url = models.CharField(max_length=255, blank=True, default="", verbose_name="Liên kết thẻ")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Mục danh mục nổi bật"
        verbose_name_plural = "Mục danh mục nổi bật"
        ordering = ["sort_order", "id"]


class HomeServiceCommitmentItem(models.Model):
    content = models.ForeignKey(
        HomePageContent,
        on_delete=models.CASCADE,
        related_name="service_commitments",
        verbose_name="Nội dung trang chủ",
    )
    title = models.CharField(max_length=120, verbose_name="Tiêu đề thẻ")
    body = models.TextField(blank=True, default="", verbose_name="Nội dung")
    icon_class = models.CharField(max_length=120, default="fas fa-certificate", verbose_name="Lớp CSS biểu tượng")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    is_active = models.BooleanField(default=True, verbose_name="Đang hiển thị")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Giá trị cam kết trang chủ"
        verbose_name_plural = "Giá trị cam kết trang chủ"
        ordering = ["sort_order", "id"]


class NewsArticle(models.Model):
    title = models.CharField(max_length=255, verbose_name="Tiêu đề")
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name="Đường dẫn")
    summary = models.TextField(blank=True, default="", verbose_name="Tóm tắt")
    content = models.TextField(blank=True, default="", verbose_name="Nội dung chi tiết")
    cover_image = models.ImageField(upload_to="news/", verbose_name="Ảnh đại diện", null=True, blank=True)
    is_published = models.BooleanField(default=True, verbose_name="Đã xuất bản")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm xuất bản")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_articles_created",
        verbose_name="Người tạo",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_articles_updated",
        verbose_name="Người cập nhật",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Thời điểm cập nhật")

    def _build_unique_slug(self):
        base_slug = slugify(self.slug or self.title or "", allow_unicode=False) or f"tin-tuc-{uuid4().hex[:8]}"
        candidate = base_slug
        suffix = 2
        while NewsArticle.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        return candidate

    def save(self, *args, **kwargs):
        self.slug = self._build_unique_slug()
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def author_display_name(self):
        user = self.updated_by or self.created_by
        if not user:
            return "GIS Pharma"
        profile = getattr(user, "profile", None)
        if profile and (profile.full_name or "").strip():
            return profile.full_name.strip()
        return (user.get_full_name() or user.first_name or user.username).strip()

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Tin tức"
        verbose_name_plural = "Tin tức"
        ordering = ["-published_at", "-created_at", "-id"]


class Pharmacy(models.Model):
    name = models.CharField(max_length=200, verbose_name="Ten nha thuoc")
    address = models.CharField(max_length=255, verbose_name="Dia chi")
    phone = models.CharField(max_length=20, verbose_name="So dien thoai", default="090xxxxxxx")
    opening_hours = models.CharField(max_length=100, verbose_name="Gio mo cua", default="8:00 - 22:00")
    desc = models.TextField(verbose_name="Mo ta dich vu", blank=True)
    image = models.ImageField(upload_to="pharmacies/", verbose_name="Hinh anh", null=True, blank=True)
    gallery_urls = models.TextField(verbose_name="Bo suu tap anh", blank=True)
    lat = models.FloatField(verbose_name="Vi do")
    lng = models.FloatField(verbose_name="Kinh do")

    def __str__(self):
        return self.name

    @property
    def has_available_medicines(self):
        return self.medicines.filter(quantity__gt=0).exists()

    @property
    def gallery_only_image_list(self):
        return build_gallery_urls_from_text(self.gallery_urls)

    @property
    def gallery_image_list(self):
        return build_gallery_urls(self)

    @property
    def primary_image_url(self):
        return self.gallery_image_list[0] if self.gallery_image_list else ""

    @property
    def average_rating(self):
        return round(self.reviews.aggregate(avg=Avg('rating')).get('avg') or 0, 1)

    @property
    def review_count(self):
        return self.reviews.count()

    class Meta:
        verbose_name = "Chi nhanh"
        verbose_name_plural = "Quan ly Chi nhanh"
        ordering = ["name"]


class PharmacyReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pharmacy_reviews")
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        verbose_name="So sao",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(verbose_name="Cam nhan", blank=True)
    is_edited = models.BooleanField(default=False, verbose_name="Da cap nhat lai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.pharmacy.name} ({self.rating} sao)"

    @property
    def was_updated_by_user(self):
        return bool(self.is_edited)

    class Meta:
        verbose_name = "Danh gia chi nhanh"
        verbose_name_plural = "Danh gia chi nhanh"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "pharmacy"], name="unique_user_pharmacy_review"),
        ]


class Medicine(models.Model):
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="medicines",
        verbose_name="Thuoc chi nhanh",
    )
    name = models.CharField(max_length=200, verbose_name="Ten thuoc")
    product_type = models.CharField(
        max_length=20,
        choices=MEDICINE_PRODUCT_TYPE_CHOICES,
        default=MEDICINE_PRODUCT_TYPE_MEDICINE,
        verbose_name="Loai san pham",
    )
    category = models.CharField(max_length=100, verbose_name="Danh muc", blank=True)
    unit = models.CharField(max_length=50, verbose_name="Don vi tinh", default="Hop")
    manufacturer = models.CharField(max_length=150, verbose_name="Nha san xuat", blank=True)
    origin = models.CharField(max_length=150, verbose_name="Xuat xu", blank=True)
    price = models.IntegerField(verbose_name="Don gia (VND)")
    quantity = models.PositiveIntegerField(verbose_name="So luong ton kho", default=0)
    image = models.ImageField(upload_to="medicines/", verbose_name="Anh thuoc", null=True, blank=True)
    gallery_urls = models.TextField(verbose_name="Bo suu tap anh", blank=True)
    short_description = models.CharField(max_length=280, verbose_name="Mo ta ngan hien thi ngoai danh sach", blank=True, default="")
    description = models.TextField(verbose_name="Mo ta chi tiet", blank=True)
    usage = models.TextField(verbose_name="Cong dung", blank=True)
    ingredients = models.TextField(verbose_name="Thanh phan", blank=True)
    dosage = models.TextField(verbose_name="Cach dung", blank=True)
    prescription_required = models.BooleanField(verbose_name="Can ke don", default=False)
    expiry_date = models.DateField(verbose_name="Han su dung", null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.quantity > 0

    @property
    def gallery_only_image_list(self):
        return build_gallery_urls_from_text(self.gallery_urls)

    @property
    def gallery_image_list(self):
        return build_gallery_urls(self)

    @property
    def primary_image_url(self):
        return self.gallery_image_list[0] if self.gallery_image_list else ""

    @property
    def average_rating(self):
        return round(self.reviews.aggregate(avg=Avg('rating')).get('avg') or 0, 1)

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def expiry_status(self):
        if not self.expiry_date:
            return "unknown"
        today = timezone.localdate()
        if self.expiry_date < today:
            return "expired"
        six_months_later = today + timedelta(days=183)
        if self.expiry_date <= six_months_later:
            return "warning"
        return "safe"

    @property
    def expiry_days_remaining(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    def get_active_promotion(self, *, on_date=None):
        today = on_date or timezone.localdate()
        prefetched = getattr(self, '_prefetched_active_promotions', None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None

        catalog_promotion = getattr(self, '_catalog_group_active_promotion', None)
        if catalog_promotion is not None:
            return catalog_promotion

        target_key = build_medicine_catalog_key(self.name, self.unit, self.manufacturer)
        promotions = MedicinePromotion.objects.select_related('medicine').filter(
            is_active=True,
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=today),
            Q(end_date__isnull=True) | Q(end_date__gte=today),
        ).order_by('-discount_percent', '-id')

        for promotion in promotions:
            medicine = getattr(promotion, 'medicine', None)
            if medicine is None:
                continue
            if build_medicine_catalog_key(medicine.name, medicine.unit, medicine.manufacturer) == target_key:
                self._catalog_group_active_promotion = promotion
                return promotion

        self._catalog_group_active_promotion = None
        return None

    @property
    def active_promotion(self):
        return self.get_active_promotion()

    @property
    def current_price(self):
        promotion = self.get_active_promotion()
        if not promotion:
            return self.price
        discounted = int(self.price * (100 - promotion.discount_percent) / 100)
        return max(discounted, 0)

    @property
    def has_active_discount(self):
        return self.current_price < self.price

    @property
    def discount_percent(self):
        promotion = self.get_active_promotion()
        return promotion.discount_percent if promotion else 0

    class Meta:
        verbose_name = "San pham thuoc"
        verbose_name_plural = "Kho Thuoc va San pham"
        ordering = ["name"]


class MedicinePromotion(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="promotions", verbose_name="Sản phẩm áp dụng")
    title = models.CharField(max_length=150, blank=True, default="", verbose_name="Tên chương trình")
    discount_percent = models.PositiveSmallIntegerField(verbose_name="Phần trăm giảm", validators=[MinValueValidator(0), MaxValueValidator(100)])
    start_date = models.DateField(null=True, blank=True, verbose_name="Ngày bắt đầu")
    end_date = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc")
    is_active = models.BooleanField(default=True, verbose_name="Đang áp dụng")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chú")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="medicine_promotions", verbose_name="Người tạo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Giảm {self.discount_percent}% - {self.medicine.name}"

    @property
    def is_currently_active(self):
        today = timezone.localdate()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

    @property
    def resolved_title(self):
        return (self.title or '').strip() or f"Giảm {self.discount_percent}%"

    class Meta:
        verbose_name = "Khuyến mãi sản phẩm"
        verbose_name_plural = "Khuyến mãi sản phẩm"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["is_active", "start_date", "end_date"], name="idx_medpromo_active"),
        ]


class MedicineReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="medicine_reviews")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        verbose_name="So sao",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(verbose_name="Cam nhan", blank=True)
    is_edited = models.BooleanField(default=False, verbose_name="Da cap nhat lai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.medicine.name} ({self.rating} sao)"

    @property
    def was_updated_by_user(self):
        return bool(self.is_edited)

    class Meta:
        verbose_name = "Danh gia san pham"
        verbose_name_plural = "Danh gia san pham"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "medicine"], name="unique_user_medicine_review"),
        ]


class StoredMediaFile(models.Model):
    file_name = models.CharField(max_length=500, unique=True, db_index=True)
    content_type = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    file_data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.file_name

    @property
    def public_url(self):
        return build_db_media_url(self.file_name)

    class Meta:
        verbose_name = "Tệp media trong PostgreSQL"
        verbose_name_plural = "Tệp media trong PostgreSQL"
        ordering = ["file_name"]


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.select_related("medicine").all())

    class Meta:
        verbose_name = "Gio hang tam"
        verbose_name_plural = "Gio hang dang hoat dong"
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=Q(session_key__isnull=False),
                name="unique_cart_session_key",
            ),
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def unit_price(self):
        return self.medicine.current_price

    @property
    def original_unit_price(self):
        return self.medicine.price

    @property
    def has_discount(self):
        return self.unit_price < self.original_unit_price

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    class Meta:
        verbose_name = "San pham trong gio"
        verbose_name_plural = "San pham trong gio"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "medicine"], name="unique_cart_medicine")
        ]


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SHIPPING = "shipping"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Chờ xử lý"),
        (STATUS_SHIPPING, "Đang giao hàng"),
        (STATUS_COMPLETED, "Hoàn thành"),
        (STATUS_CANCELLED, "Đã hủy"),
    )

    PAYMENT_COD = "cod"
    PAYMENT_MOMO = "momo"
    PAYMENT_BANK = "bank"
    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_COD, "Thanh toán khi nhận hàng (COD)"),
        (PAYMENT_MOMO, "Vi MoMo"),
        (PAYMENT_BANK, "Chuyển khoản ngân hàng"),
    )

    PAYMENT_STATUS_COD_WAITING = "cod_waiting"
    PAYMENT_STATUS_AWAITING_TRANSFER = "awaiting_transfer"
    PAYMENT_STATUS_PAID = "paid"
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_STATUS_COD_WAITING, "Thu tiền khi giao hàng"),
        (PAYMENT_STATUS_AWAITING_TRANSFER, "Chờ xác nhận thanh toán"),
        (PAYMENT_STATUS_PAID, "Đã thanh toán"),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tai khoan khach")
    full_name = models.CharField(max_length=100, verbose_name="Nguoi nhan")
    phone = models.CharField(max_length=20, verbose_name="SDT lien he")
    address_text = models.CharField(max_length=255, verbose_name="Dia chi giao")
    note = models.TextField(verbose_name="Ghi chu cua khach", blank=True, null=True)

    delivery_lat = models.FloatField(verbose_name="Vi do", null=True, blank=True)
    delivery_lng = models.FloatField(verbose_name="Kinh do", null=True, blank=True)

    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.SET_NULL, null=True, verbose_name="Chi nhanh xu ly")

    distance_km = models.FloatField(default=0, verbose_name="Khoang cach (km)")
    shipping_fee = models.IntegerField(default=0, verbose_name="Phi ship")
    total_product_price = models.IntegerField(default=0, verbose_name="Tien hang")
    final_total_price = models.IntegerField(default=0, verbose_name="Tong thanh toan")
    customer_tier_name = models.CharField(max_length=40, blank=True, default="", verbose_name="Hang khach hang luc dat")
    customer_tier_discount_percent = models.PositiveSmallIntegerField(default=0, verbose_name="Muc giam theo hang KH (%)")
    customer_tier_discount_total = models.PositiveIntegerField(default=0, verbose_name="Tong tien giam theo hang KH")

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_COD,
        verbose_name="Phuong thuc thanh toan",
    )
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_COD_WAITING,
        verbose_name="Trang thai thanh toan",
    )
    payment_reference = models.CharField(max_length=120, blank=True, default="", verbose_name="Ma tham chieu thanh toan")
    invoice_requested = models.BooleanField(default=False, verbose_name="Khach yeu cau xuat hoa don")
    invoice_code = models.CharField(max_length=40, blank=True, default="", db_index=True, verbose_name="Ma hoa don")
    invoice_staff_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Nhan vien lap hoa don")

    estimated_delivery_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian giao du kien")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian hoan thanh")
    received_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Khach xac nhan da nhan")
    auto_completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tu dong hoan thanh")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian huy")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Trang thai don")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian dat")

    def __str__(self):
        return f"Don #{self.id} - {self.full_name}"

    @property
    def order_code(self):
        if self.pk:
            return f"DH{self.pk:06d}"
        return "DH-TAM"

    @property
    def resolved_invoice_code(self):
        return self.invoice_code or (f"HD{self.created_at.strftime('%Y%m%d')}-{self.pk:06d}" if self.pk and self.created_at else "HD-TAM")

    @property
    def resolved_payment_reference(self):
        return self.payment_reference or self.order_code

    @property
    def auto_complete_deadline_at(self):
        base_dt = self.estimated_delivery_at or self.created_at
        if not base_dt:
            return None
        return base_dt + timedelta(days=5)

    @property
    def can_customer_cancel(self):
        return self.status == self.STATUS_PENDING

    @property
    def can_customer_confirm_received(self):
        return self.status == self.STATUS_SHIPPING

    @property
    def can_request_return_refund(self):
        return self.status == self.STATUS_COMPLETED

    @property
    def has_customer_tier_discount(self):
        return self.customer_tier_discount_percent > 0 and self.customer_tier_discount_total > 0

    @property
    def product_subtotal_before_tier_discount(self):
        return int(self.total_product_price or 0) + int(self.customer_tier_discount_total or 0)

    @property
    def resolved_invoice_staff_name(self):
        staff_name = (self.invoice_staff_name or "").strip()
        if staff_name:
            normalized_staff_name = staff_name.casefold()
            matched_profile = UserProfile.objects.select_related("user").filter(
                Q(full_name__iexact=staff_name) | Q(user__username__iexact=staff_name)
            ).order_by("id").first()
            if matched_profile:
                candidate = (matched_profile.full_name or "").strip()
                if not candidate and matched_profile.user:
                    candidate = (
                        matched_profile.user.get_full_name().strip()
                        or matched_profile.user.first_name.strip()
                        or matched_profile.user.username
                    )
                if candidate:
                    return candidate
            if normalized_staff_name != "nhân viên quầy thuốc":
                return staff_name

        pharmacy = getattr(self, "pharmacy", None)
        if pharmacy:
            profile = pharmacy.managed_staff_profiles.select_related("user").order_by("id").first()
            if profile:
                candidate = (profile.full_name or "").strip()
                if not candidate and profile.user:
                    candidate = (profile.user.get_full_name() or profile.user.first_name or "").strip()
                if candidate:
                    return candidate
        return staff_name or "Nhân viên quầy thuốc"

    class Meta:
        verbose_name = "Don hang"
        verbose_name_plural = "Xu ly Don hang"
        ordering = ["-created_at", "-id"]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True)
    medicine_name = models.CharField(max_length=200)
    price = models.IntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.price * self.quantity

    class Meta:
        verbose_name = "Chi tiet san pham"
        verbose_name_plural = "Chi tiet san pham"


class ReturnRefundRequest(models.Model):
    STATUS_PROCESSING = "processing"
    STATUS_APPROVED = "approved_refund"
    STATUS_REJECTED = "rejected_refund"

    STATUS_CHOICES = (
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_APPROVED, "Chấp nhận hoàn tiền"),
        (STATUS_REJECTED, "Từ chối hoàn tiền"),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="return_request")
    reason = models.TextField(verbose_name="Ly do tra hang / hoan tien")
    bank_account_number = models.CharField(max_length=80, blank=True, default="", verbose_name="So tai khoan ngan hang")
    momo_account_number = models.CharField(max_length=80, blank=True, default="", verbose_name="So tai khoan MoMo")
    contact_email = models.EmailField(blank=True, default="", verbose_name="Email lien he")
    contact_phone = models.CharField(max_length=20, blank=True, default="", verbose_name="So dien thoai lien he")
    bill_image = models.ImageField(upload_to="returns/bills/", blank=True, null=True, verbose_name="Anh bill / hoa don")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING, verbose_name="Trang thai xu ly")
    admin_note = models.TextField(blank=True, default="", verbose_name="Ghi chu xu ly noi bo")
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_return_requests",
        verbose_name="Nhan vien xu ly",
    )
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian xu ly")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Yeu cau tra hang / hoan tien - Don #{self.order_id}"

    @property
    def proof_image_count(self):
        return self.evidences.count()

    @property
    def is_finalized(self):
        return self.status in {self.STATUS_APPROVED, self.STATUS_REJECTED}

    @property
    def processed_by_display_name(self):
        user = getattr(self, "processed_by", None)
        if not user:
            return ""
        profile = getattr(user, "profile", None)
        if profile and (profile.full_name or "").strip():
            return profile.full_name.strip()
        return (user.get_full_name() or user.first_name or user.username).strip()

    class Meta:
        verbose_name = "Yeu cau tra hang / hoan tien"
        verbose_name_plural = "Yeu cau tra hang / hoan tien"
        ordering = ["-created_at", "-id"]


class ReturnRefundEvidence(models.Model):
    request = models.ForeignKey(ReturnRefundRequest, on_delete=models.CASCADE, related_name="evidences")
    image = models.ImageField(upload_to="returns/evidences/", verbose_name="Anh chung minh")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anh chung minh #{self.pk} - Don #{self.request.order_id}"

    class Meta:
        verbose_name = "Anh chung minh tra hang"
        verbose_name_plural = "Anh chung minh tra hang"
        ordering = ["id"]


class PurchaseImportBatch(models.Model):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="purchase_import_batches", verbose_name="Chi nhanh nhap hang")
    invoice_code = models.CharField(max_length=80, blank=True, default="", db_index=True, verbose_name="Ma hoa don nhap")
    source_file = models.FileField(upload_to="imports/excel/", verbose_name="File Excel nhap hang")
    receipt_pdf = models.FileField(upload_to="imports/receipts/", blank=True, null=True, verbose_name="Phieu nhap PDF")
    imported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_import_batches",
        verbose_name="Nguoi phu trach nhap hang",
    )
    imported_by_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Ho ten nguoi phu trach")
    imported_by_email = models.EmailField(blank=True, default="", verbose_name="Email nguoi phu trach")
    imported_by_role = models.CharField(max_length=120, blank=True, default="", verbose_name="Chuc vu nguoi phu trach")
    note = models.TextField(blank=True, default="", verbose_name="Ghi chu")
    total_lines = models.PositiveIntegerField(default=0, verbose_name="So dong hop le")
    total_quantity = models.PositiveIntegerField(default=0, verbose_name="Tong so luong nhap")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian nhap")

    def __str__(self):
        return self.invoice_code or f"NHAP-{self.pk or 'TAM'}"

    @property
    def resolved_invoice_code(self):
        if self.invoice_code:
            return self.invoice_code
        if self.pk and self.created_at:
            return f"NHAP{self.created_at.strftime('%Y%m%d')}-{self.pk:05d}"
        return "NHAP-TAM"

    @property
    def resolved_imported_by_name(self):
        raw_name = (self.imported_by_name or "").strip()
        user = getattr(self, "imported_by", None)
        if user:
            profile = getattr(user, "profile", None)
            if profile and (profile.full_name or "").strip():
                return profile.full_name.strip()
            candidate = (user.get_full_name() or user.first_name or "").strip()
            if candidate:
                return candidate
            if raw_name and raw_name.casefold() != user.username.casefold():
                return raw_name
            return user.username
        return raw_name or "Nhân viên nhập hàng"

    class Meta:
        verbose_name = "Phieu nhap hang"
        verbose_name_plural = "Nhap hang bang Excel"
        ordering = ["-created_at", "-id"]


class PurchaseImportItem(models.Model):
    batch = models.ForeignKey(PurchaseImportBatch, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_import_items")
    medicine_name = models.CharField(max_length=200, verbose_name="Ten thuoc")
    manufacturer = models.CharField(max_length=150, blank=True, default="", verbose_name="Nha san xuat")
    unit = models.CharField(max_length=50, blank=True, default="", verbose_name="Don vi tinh")
    previous_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton truoc khi nhap")
    imported_quantity = models.PositiveIntegerField(default=0, verbose_name="So luong nhap")
    new_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton sau khi nhap")
    import_price = models.PositiveIntegerField(default=0, verbose_name="Gia nhap")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Han su dung nhap vao")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chu dong")

    def __str__(self):
        return f"{self.medicine_name} - batch #{self.batch_id}"

    class Meta:
        verbose_name = "Chi tiet nhap hang"
        verbose_name_plural = "Chi tiet nhap hang"
        ordering = ["id"]


class StockExportBatch(models.Model):
    EXPORT_SCOPE_STANDARD = "standard"
    EXPORT_SCOPE_RECONCILE = "reconcile"
    EXPORT_SCOPE_EXPIRED = "expired"
    EXPORT_SCOPE_CHOICES = (
        (EXPORT_SCOPE_STANDARD, "Xuất nội bộ / chuyển kho"),
        (EXPORT_SCOPE_RECONCILE, "Đối soát tồn vật lý"),
        (EXPORT_SCOPE_EXPIRED, "Xử lý hàng hết hạn"),
    )

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="stock_export_batches",
        verbose_name="Chi nhanh xuat kho",
    )
    export_scope = models.CharField(
        max_length=20,
        choices=EXPORT_SCOPE_CHOICES,
        default=EXPORT_SCOPE_STANDARD,
        verbose_name="Loai phieu xuat",
    )
    export_code = models.CharField(max_length=80, blank=True, default="", db_index=True, verbose_name="Ma phieu xuat")
    receipt_pdf = models.FileField(upload_to="exports/receipts/", blank=True, null=True, verbose_name="Phieu xuat PDF")
    exported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_export_batches",
        verbose_name="Nguoi lap phieu xuat",
    )
    exported_by_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Ho ten nguoi lap phieu")
    exported_by_email = models.EmailField(blank=True, default="", verbose_name="Email nguoi lap phieu")
    exported_by_role = models.CharField(max_length=120, blank=True, default="", verbose_name="Chuc vu nguoi lap phieu")
    destination_name = models.CharField(max_length=180, blank=True, default="", verbose_name="Noi nhan / muc dich xuat")
    note = models.TextField(blank=True, default="", verbose_name="Ghi chu")
    total_lines = models.PositiveIntegerField(default=0, verbose_name="So dong xuat")
    total_quantity = models.PositiveIntegerField(default=0, verbose_name="Tong so luong xuat")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian xuat")

    def __str__(self):
        return self.export_code or f"XUAT-{self.pk or 'TAM'}"

    @property
    def resolved_export_code(self):
        if self.export_code:
            return self.export_code
        if self.pk and self.created_at:
            return f"XUAT{self.created_at.strftime('%Y%m%d')}-{self.pk:05d}"
        return "XUAT-TAM"

    @property
    def resolved_exported_by_name(self):
        raw_name = (self.exported_by_name or "").strip()
        user = getattr(self, "exported_by", None)
        if user:
            profile = getattr(user, "profile", None)
            if profile and (profile.full_name or "").strip():
                return profile.full_name.strip()
            candidate = (user.get_full_name() or user.first_name or "").strip()
            if candidate:
                return candidate
            if raw_name and raw_name.casefold() != user.username.casefold():
                return raw_name
            return user.username
        return raw_name or "Nhân viên xuất kho"

    class Meta:
        verbose_name = "Phieu xuat kho"
        verbose_name_plural = "Phieu xuat kho"
        ordering = ["-created_at", "-id"]


class StockExportItem(models.Model):
    batch = models.ForeignKey(StockExportBatch, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_export_items")
    medicine_name = models.CharField(max_length=200, verbose_name="Ten san pham")
    manufacturer = models.CharField(max_length=150, blank=True, default="", verbose_name="Nha san xuat")
    unit = models.CharField(max_length=50, blank=True, default="", verbose_name="Don vi tinh")
    previous_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton truoc khi xuat")
    exported_quantity = models.PositiveIntegerField(default=0, verbose_name="So luong xuat")
    remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton sau khi xuat")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chu dong")

    def __str__(self):
        return f"{self.medicine_name} - export #{self.batch_id}"

    class Meta:
        verbose_name = "Chi tiet xuat kho"
        verbose_name_plural = "Chi tiet xuat kho"
        ordering = ["id"]


class MedicineLot(models.Model):
    SOURCE_IMPORT = "purchase_import"
    SOURCE_MANUAL = "manual_adjustment"
    SOURCE_RETURN = "return_restore"

    SOURCE_CHOICES = (
        (SOURCE_IMPORT, "Nhập hàng"),
        (SOURCE_MANUAL, "Điều chỉnh tay"),
        (SOURCE_RETURN, "Hoàn kho từ đơn hàng"),
    )

    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="lots", verbose_name="Thuốc")
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="medicine_lots", verbose_name="Chi nhánh")
    purchase_batch = models.ForeignKey(
        PurchaseImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicine_lots",
        verbose_name="Phiếu nhập nguồn",
    )
    purchase_item = models.ForeignKey(
        PurchaseImportItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicine_lots",
        verbose_name="Dòng nhập nguồn",
    )
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_IMPORT, verbose_name="Nguồn tạo lô")
    source_label = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn nguồn")
    import_price = models.PositiveIntegerField(default=0, verbose_name="Giá nhập")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Hạn sử dụng")
    received_quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng nhập lô")
    remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng còn lại")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        base = self.source_label or f"Lô #{self.pk}"
        return f"{self.medicine.name} - {base}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    @property
    def is_sellable(self):
        if self.remaining_quantity <= 0:
            return False
        if self.expiry_date and self.expiry_date < timezone.localdate():
            return False
        return True

    @property
    def expiry_days_remaining(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    class Meta:
        verbose_name = "Lô tồn kho thuốc"
        verbose_name_plural = "Lô tồn kho thuốc"
        ordering = ["expiry_date", "created_at", "id"]
        indexes = [
            models.Index(fields=["medicine", "expiry_date"], name="idx_medlot_med_exp"),
            models.Index(fields=["pharmacy", "expiry_date"], name="idx_medlot_pharm_exp"),
        ]


class OrderItemLotAllocation(models.Model):
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE, related_name="lot_allocations", verbose_name="Dòng đơn hàng")
    lot = models.ForeignKey(MedicineLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_allocations", verbose_name="Lô thuốc")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng phân bổ")
    lot_expiry_date = models.DateField(null=True, blank=True, verbose_name="HSD snapshot")
    lot_import_price = models.PositiveIntegerField(default=0, verbose_name="Giá nhập snapshot")
    lot_source_label = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn lô snapshot")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alloc order_item #{self.order_item_id} - lot #{self.lot_id or 'NA'}"

    class Meta:
        verbose_name = "Phân bổ lô cho dòng đơn"
        verbose_name_plural = "Phân bổ lô cho dòng đơn"
        ordering = ["id"]


class StockExportLotAllocation(models.Model):
    export_item = models.ForeignKey(StockExportItem, on_delete=models.CASCADE, related_name="lot_allocations", verbose_name="Dòng phiếu xuất")
    lot = models.ForeignKey(MedicineLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_export_allocations", verbose_name="Lô thuốc")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng phân bổ")
    lot_expiry_date = models.DateField(null=True, blank=True, verbose_name="HSD snapshot")
    lot_import_price = models.PositiveIntegerField(default=0, verbose_name="Giá nhập snapshot")
    lot_source_label = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn lô snapshot")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alloc export_item #{self.export_item_id} - lot #{self.lot_id or 'NA'}"

    class Meta:
        verbose_name = "Phân bổ lô cho phiếu xuất"
        verbose_name_plural = "Phân bổ lô cho phiếu xuất"
        ordering = ["id"]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=150, verbose_name="Ho ten hien thi", blank=True)
    phone = models.CharField(max_length=20, verbose_name="So dien thoai", blank=True)
    address_text = models.CharField(max_length=255, verbose_name="Dia chi mac dinh", blank=True)
    address_lat = models.FloatField(verbose_name="Vi do mac dinh", null=True, blank=True)
    address_lng = models.FloatField(verbose_name="Kinh do mac dinh", null=True, blank=True)
    managed_pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.SET_NULL,
        related_name="managed_staff_profiles",
        verbose_name="Chi nhanh lam viec",
        null=True,
        blank=True,
    )
    admin_permissions = models.JSONField(default=dict, blank=True, verbose_name="Phan quyen quan tri chi tiet")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.username

    @property
    def has_saved_address(self):
        return bool(self.address_text and self.address_lat is not None and self.address_lng is not None)

    class Meta:
        verbose_name = "Ho so tai khoan"
        verbose_name_plural = "Ho so tai khoan"


class AccountOtpChallenge(models.Model):
    PURPOSE_PASSWORD_RESET = "password_reset"
    PURPOSE_USERNAME_RECOVERY = "username_recovery"
    PURPOSE_CHOICES = (
        (PURPOSE_PASSWORD_RESET, "Đặt lại mật khẩu"),
        (PURPOSE_USERNAME_RECOVERY, "Khôi phục tên đăng nhập"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="account_otp_challenges",
        verbose_name="Tài khoản",
    )
    purpose = models.CharField(
        max_length=40,
        choices=PURPOSE_CHOICES,
        db_index=True,
        verbose_name="Mục đích xác thực",
    )
    email = models.EmailField(db_index=True, verbose_name="Email nhận mã")
    public_token = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name="Mã công khai của phiên OTP",
    )
    otp_hash = models.CharField(max_length=255, verbose_name="Mã OTP đã băm")
    username_snapshot = models.CharField(max_length=150, blank=True, default="", verbose_name="Tên đăng nhập snapshot")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Thời điểm hết hạn")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Số lần nhập sai")
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm đã dùng xong")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Thời điểm cập nhật")

    def __str__(self):
        return f"{self.get_purpose_display()} - {self.email}"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_active(self):
        return not self.is_consumed and not self.is_expired

    class Meta:
        verbose_name = "Phiên OTP khôi phục tài khoản"
        verbose_name_plural = "Phiên OTP khôi phục tài khoản"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["purpose", "email"], name="idx_otp_purpose_email"),
            models.Index(fields=["user", "purpose"], name="idx_otp_user_purpose"),
        ]
