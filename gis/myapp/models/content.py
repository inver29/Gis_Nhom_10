from uuid import uuid4
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


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

