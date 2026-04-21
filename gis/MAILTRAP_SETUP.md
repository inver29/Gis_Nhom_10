# Mailtrap Setup Cho GIS Pharma

## 1. Chon dung loai Mailtrap

- `Email Testing`: chi de test trong qua trinh phat trien. Email se vao inbox Mailtrap, khong vao hop thu that cua khach hang.
- `Email Sending`: gui den email that cua khach hang. Neu ban muon khach nhan thong bao don hang, hoan tien, quen mat khau, quen ten dang nhap, hay dung muc nay.

## 2. Trong project nay da ho tro cac email nao

- Cap nhat trang thai don hang khi admin doi trang thai.
- Cap nhat yeu cau tra hang / hoan tien khi admin doi trang thai.
- Quen mat khau.
- Quen ten dang nhap: email gui ten dang nhap kem lien ket dat lai mat khau.

## 3. Thong so can lay tu Mailtrap

Trong Mailtrap, vao phan SMTP credentials va copy:

- SMTP host
- SMTP port
- Username
- Password

Neu ban dung `Email Sending`, hay kiem tra them:

- Domain gui mail da duoc verify
- Dia chi `from email` dung domain da verify

## 4. Cac bien moi truong ma project dang doc

Project dang doc cac bien sau trong `gis/settings.py`:

- `MAILTRAP_HOST`
- `MAILTRAP_PORT`
- `MAILTRAP_USERNAME`
- `MAILTRAP_PASSWORD`
- `MAILTRAP_USE_TLS`
- `DEFAULT_FROM_EMAIL`
- `SITE_NAME`
- `SITE_SUPPORT_EMAIL`
- `SITE_BASE_URL`

## 5. Cach set nhanh tren Windows PowerShell

Vi du voi local:

```powershell
$env:MAILTRAP_HOST='sandbox.smtp.mailtrap.io'
$env:MAILTRAP_PORT='2525'
$env:MAILTRAP_USERNAME='YOUR_MAILTRAP_USERNAME'
$env:MAILTRAP_PASSWORD='YOUR_MAILTRAP_PASSWORD'
$env:MAILTRAP_USE_TLS='true'
$env:DEFAULT_FROM_EMAIL='GIS Pharma <no-reply@example.com>'
$env:SITE_NAME='GIS Pharma'
$env:SITE_SUPPORT_EMAIL='support@example.com'
$env:SITE_BASE_URL='http://127.0.0.1:8000'
python manage.py runserver
```

Neu ban dung `Email Sending`, thay host/port/username/password va `DEFAULT_FROM_EMAIL` bang thong so trong muc `Email Sending`.

## 6. Kiem tra sau khi bat Mailtrap

1. Dang ky mot tai khoan co email that hoac email test.
2. Dang nhap admin.
3. Doi trang thai mot don hang.
4. Doi trang thai mot yeu cau tra hang / hoan tien.
5. Thu `Quen mat khau`.
6. Thu `Quen ten dang nhap`.

## 7. Luu y quan trong

- Neu ban dang dung `Email Testing`, khach hang that se khong nhan duoc mail.
- Neu ban muon gui ra ngoai that, can dung `Email Sending` hoac nha cung cap SMTP that.
- `DEFAULT_FROM_EMAIL` nen dung dia chi hop le theo domain gui da xac minh.
