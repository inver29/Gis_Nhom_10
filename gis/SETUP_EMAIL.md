# Setup gửi email — LÀM 1 LẦN DUY NHẤT, sau đó quên luôn

## Bước 1 — Chạy block sau **MỘT LẦN DUY NHẤT** trong PowerShell

Trước khi dán: thay `DAN_APP_PASSWORD_VAO_DAY` bằng App Password Gmail thật (16 ký tự liền, bỏ khoảng trắng).

Mở PowerShell (ở đâu cũng được, không cần ở thư mục project), dán block dưới rồi Enter:

```powershell
[Environment]::SetEnvironmentVariable('EMAIL_HOST','smtp.gmail.com','User')
[Environment]::SetEnvironmentVariable('EMAIL_PORT','587','User')
[Environment]::SetEnvironmentVariable('EMAIL_HOST_USER','cuahangduocpham.notify@gmail.com','User')
[Environment]::SetEnvironmentVariable('EMAIL_HOST_PASSWORD','DAN_APP_PASSWORD_VAO_DAY','User')
[Environment]::SetEnvironmentVariable('EMAIL_USE_TLS','true','User')
[Environment]::SetEnvironmentVariable('EMAIL_USE_SSL','false','User')
[Environment]::SetEnvironmentVariable('DEFAULT_FROM_EMAIL','GIS Pharma <cuahangduocpham.notify@gmail.com>','User')
[Environment]::SetEnvironmentVariable('SITE_SUPPORT_EMAIL','cuahangduocpham.notify@gmail.com','User')
[Environment]::SetEnvironmentVariable('SITE_BASE_URL','http://127.0.0.1:8000','User')
```

→ Block này lưu thông tin vào registry user của Windows. Lưu vĩnh viễn. Không phải làm lại.

## Bước 2 — Đóng tất cả PowerShell, mở lại

Bắt buộc — env vars chỉ load khi mở terminal mới.

## Bước 3 — Test xem lưu được chưa

Mở PowerShell mới, gõ:

```powershell
echo $env:EMAIL_HOST_USER
echo $env:EMAIL_HOST_PASSWORD
```

Phải in ra Gmail và App Password. Nếu rỗng → quay lại Bước 1.

## Từ giờ về sau, mỗi lần chạy server chỉ cần:

```powershell
cd c:\GISS_CK_2\GIS_CUOI_KY_II\Gis_Nhom_10\gis
run
```

Gõ đúng 1 chữ `run`, Enter là xong. Không cần dán gì nữa hết.

## Muốn xóa thông tin sau này?

```powershell
[Environment]::SetEnvironmentVariable('EMAIL_HOST_PASSWORD',$null,'User')
```
