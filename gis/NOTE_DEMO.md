# NOTE CÁC CHỨC NĂNG CHÍNH ĐÃ LÀM

> Note này dùng để nói cuối video demo, tổng kết các chức năng chính nhóm đã thực hiện.

---

## 1. Hệ thống tài khoản & xác thực
- Đăng ký tài khoản có **xác thực OTP qua email** + link kích hoạt.
- Đăng nhập / đăng xuất.
- **Quên mật khẩu** và **khôi phục tên đăng nhập** qua email OTP.
- Quản lý **hồ sơ cá nhân** (thông tin, địa chỉ, đổi mật khẩu).

## 2. Trang nội dung (Front-end khách hàng)
- Trang chủ, trang Giới thiệu (admin tự cấu hình banner, slide, khối nội dung).
- **Tin tức**: danh sách + chi tiết bài viết.
- Danh mục **sản phẩm thuốc / thực phẩm chức năng** (tìm kiếm, lọc, phân loại).
- **Chi tiết thuốc**: thông tin, ảnh gallery, đánh giá – bình luận, gợi ý liên quan.

## 3. GIS – Bản đồ & định vị (chức năng trọng tâm)
- **Bản đồ chi nhánh nhà thuốc** hiển thị toàn bộ pharmacy.
- **Tìm nhà thuốc gần nhất** theo vị trí người dùng.
- **Tìm nhà thuốc tốt nhất có sẵn thuốc** người dùng cần (kết hợp khoảng cách + tồn kho).
- **Vẽ tuyến đường** (routing) từ vị trí người dùng đến nhà thuốc.
- API **tìm kiếm địa chỉ** & **reverse-geocoding** (nhập địa chỉ → tọa độ và ngược lại).
- Trang **chi tiết nhà thuốc**: thông tin, gallery, đánh giá, danh sách thuốc có sẵn.

## 4. Mua hàng – Đặt hàng
- **Giỏ hàng**: thêm / sửa số lượng / xoá.
- **Đặt hàng nhanh** (quick order).
- **Thanh toán (checkout)** với preview chi phí (ship, giảm giá…).
- **Đơn có kê đơn** – upload ảnh đơn thuốc, quy trình duyệt riêng.
- **Upload chứng từ thanh toán** (chuyển khoản).
- **Lịch sử đơn hàng**: chi tiết, hoá đơn, huỷ đơn, xác nhận đã nhận.
- **Yêu cầu trả hàng / hoàn tiền** kèm bằng chứng.

## 5. Email tự động
- Gửi email cho: kích hoạt tài khoản, OTP đăng ký, khôi phục tài khoản, đổi mật khẩu, cập nhật hồ sơ, xác nhận đơn, cập nhật trạng thái đơn, xác nhận thanh toán, hoá đơn, huỷ đơn, yêu cầu trả hàng, cập nhật trạng thái trả hàng.

## 6. Trang quản trị (Custom Admin Panel)
- **Dashboard** thống kê tổng quan.
- **Quản lý đơn hàng** + chi tiết đơn (duyệt, đổi trạng thái).
- **Quản lý kho – Inventory**:
  - **Phiếu nhập kho** (purchase import) + in phiếu.
  - **Phiếu xuất kho** (stock export) + in phiếu + xuất Excel.
  - Quản lý **lô hàng** (medicine lot) – theo dõi hạn dùng, số lô.
- **Quản lý yêu cầu trả hàng**.
- **Quản lý nội dung**: trang chủ, trang Giới thiệu, tin tức (có rich-text editor + upload ảnh).
- **Báo cáo / Analytics** + **xuất Excel báo cáo**.
- **Review insights** – phân tích đánh giá khách hàng.
- **Phân quyền** (permissions center).
- CRUD chung cho các model còn lại.

## 7. Một vài điểm kỹ thuật nổi bật
- Lưu media (ảnh) trực tiếp **trong database** (StoredMediaFile) thay vì chỉ trên ổ đĩa.
- Trình **soạn thảo rich-text** có upload ảnh trực tiếp.
- **Xuất Excel** cho phiếu xuất kho và báo cáo.
- **Middleware & signals** xử lý nghiệp vụ tự động (đồng bộ tồn kho, gửi mail, log…).
- Trang **error preview** (xem trước trang lỗi 404, 500…).

---

### Gợi ý trình tự nói cuối video (~30 giây)
> "Tóm lại, các chức năng chính nhóm đã làm gồm: hệ thống tài khoản có OTP qua email, GIS bản đồ với tìm nhà thuốc gần nhất và vẽ tuyến đường, danh mục sản phẩm – đánh giá, giỏ hàng – đặt hàng – đơn có kê đơn, lịch sử đơn và yêu cầu trả hàng, cùng với trang quản trị đầy đủ: quản lý đơn, kho (nhập – xuất – lô hàng), nội dung, báo cáo Excel và phân quyền. Hệ thống cũng tích hợp email tự động cho toàn bộ luồng nghiệp vụ."
