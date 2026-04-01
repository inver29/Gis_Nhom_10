BEGIN;

SET TIME ZONE 'Asia/Ho_Chi_Minh';

DELETE FROM myapp_orderitem WHERE order_id BETWEEN 9401 AND 9412;
DELETE FROM myapp_order WHERE id BETWEEN 9401 AND 9412;
DELETE FROM myapp_cartitem WHERE cart_id BETWEEN 9301 AND 9303;
DELETE FROM myapp_cart WHERE id BETWEEN 9301 AND 9303;
DELETE FROM myapp_medicine WHERE id BETWEEN 9201 AND 9296;
DELETE FROM myapp_pharmacy WHERE id BETWEEN 9101 AND 9112;
DELETE FROM myapp_userprofile WHERE user_id BETWEEN 9001 AND 9010;
DELETE FROM auth_user WHERE id BETWEEN 9001 AND 9010;

INSERT INTO auth_user (
    id, password, last_login, is_superuser, username, first_name, last_name,
    email, is_staff, is_active, date_joined
) VALUES
    (9001, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, TRUE,  'admin_master',   'Nguyen Quan Tri', '', 'admin@gispharma.local',   TRUE,  TRUE, '2026-03-01 08:00:00+07'),
    (9002, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'manager_q3',     'Tran Duoc Si',   '', 'manager.q3@gispharma.local', TRUE, TRUE, '2026-03-02 08:00:00+07'),
    (9003, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'manager_q10',    'Le Van Kho',     '', 'manager.q10@gispharma.local', TRUE, TRUE, '2026-03-02 08:30:00+07'),
    (9004, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_anh',   'Nguyen Thi Anh', '', 'anh@gmail.com', FALSE, TRUE, '2026-03-03 09:00:00+07'),
    (9005, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_binh',  'Pham Quoc Binh', '', 'binh@gmail.com', FALSE, TRUE, '2026-03-03 09:15:00+07'),
    (9006, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_lan',   'Vo Thi Lan',     '', 'lan@gmail.com', FALSE, TRUE, '2026-03-03 09:30:00+07'),
    (9007, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_minh',  'Do Minh Tam',    '', 'minh@gmail.com', FALSE, TRUE, '2026-03-03 10:00:00+07'),
    (9008, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_ngoc',  'Tran Ngoc Ha',   '', 'ngoc@gmail.com', FALSE, TRUE, '2026-03-03 10:15:00+07'),
    (9009, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_phuc',  'Le Hoang Phuc',  '', 'phuc@gmail.com', FALSE, TRUE, '2026-03-03 10:30:00+07'),
    (9010, 'pbkdf2_sha256$1000000$gispharma2026$t9SeGxidVfxWACT7trXd+b5yHgoh/XeQKJlHTpJN3oA=', NULL, FALSE, 'customer_tram',  'Hoang Bao Tram', '', 'tram@gmail.com', FALSE, TRUE, '2026-03-03 10:45:00+07');

INSERT INTO myapp_userprofile (
    id, user_id, full_name, phone, address_text, address_lat, address_lng, updated_at
) VALUES
    (9901, 9001, 'Nguyen Quan Tri', '0909000001', '', NULL, NULL, NOW()),
    (9902, 9002, 'Tran Duoc Si', '0909000002', '', NULL, NULL, NOW()),
    (9903, 9003, 'Le Van Kho', '0909000003', '', NULL, NULL, NOW()),
    (9904, 9004, 'Nguyen Thi Anh', '0901234567', '12 Nguyen Hue, Ben Nghe, Quan 1, TP.HCM', 10.773255, 106.704777, NOW()),
    (9905, 9005, 'Pham Quoc Binh', '0902345678', '44 Le Van Sy, Phuong 14, Quan 3, TP.HCM', 10.786564, 106.678626, NOW()),
    (9906, 9006, 'Vo Thi Lan', '0903456789', '211 Au Co, Phuong 5, Quan 11, TP.HCM', 10.764893, 106.648717, NOW()),
    (9907, 9007, 'Do Minh Tam', '0904567890', '88 Nguyen Xi, Phuong 26, Binh Thanh, TP.HCM', 10.812647, 106.709027, NOW()),
    (9908, 9008, 'Tran Ngoc Ha', '0905678901', '102 Kha Van Can, Linh Chieu, Thu Duc, TP.HCM', 10.849679, 106.761522, NOW()),
    (9909, 9009, 'Le Hoang Phuc', '0906789012', '341 Huynh Tan Phat, Tan Thuan Dong, Quan 7, TP.HCM', 10.742113, 106.734560, NOW()),
    (9910, 9010, 'Hoang Bao Tram', '0907890123', '145 Lu Gia, Phuong 15, Quan 11, TP.HCM', 10.767662, 106.657854, NOW());

INSERT INTO myapp_pharmacy (
    id, name, address, phone, opening_hours, "desc", image, gallery_urls, lat, lng
) VALUES
    (9101, 'Pharmacy - Quan 1', '123 Tran Hung Dao, Phuong Co Ong Lanh, Quan 1, TP.HCM', '02839210001', '07:00 - 22:30', 'Chi nhanh trung tam, phu hop don giao nhanh noi thanh.', 'seed/pharmacies/storefront-blue.svg', E'/media/seed/pharmacies/storefront-blue.svg\n/media/seed/pharmacies/interior.svg\n/media/seed/pharmacies/storefront-green.svg', 10.763782, 106.696376),
    (9102, 'Pharmacy - Quan 3', '456 Le Van Sy, Phuong 14, Quan 3, TP.HCM', '02839210002', '07:00 - 22:00', 'Chi nhanh gan khu dan cu va nhieu tuyen giao thong lon.', 'seed/pharmacies/storefront-green.svg', E'/media/seed/pharmacies/storefront-green.svg\n/media/seed/pharmacies/interior.svg\n/media/seed/pharmacies/storefront-blue.svg', 10.786152, 106.678208),
    (9103, 'Nha Thuoc An Khang - Quan 10', '789 Duong 3/2, Phuong 12, Quan 10, TP.HCM', '02839210003', '07:30 - 22:00', 'Chi nhanh co luu luong don thuoc va thuc pham chuc nang cao.', 'seed/pharmacies/storefront-blue.svg', E'/media/seed/pharmacies/storefront-blue.svg\n/media/seed/pharmacies/interior.svg', 10.776812, 106.664799),
    (9104, 'MediPlus - Go Vap', '88 Quang Trung, Phuong 10, Go Vap, TP.HCM', '02839210004', '07:00 - 22:00', 'Chi nhanh phuc vu khu vuc phia Bac thanh pho.', 'seed/pharmacies/storefront-green.svg', E'/media/seed/pharmacies/storefront-green.svg\n/media/seed/pharmacies/interior.svg', 10.836164, 106.664780),
    (9105, 'HealthyLife - Binh Thanh', '201 Dien Bien Phu, Phuong 15, Binh Thanh, TP.HCM', '02839210005', '07:00 - 22:00', 'Chi nhanh co ton kho manh cho khu vuc noi thanh va gan trung tam.', 'seed/pharmacies/storefront-blue.svg', E'/media/seed/pharmacies/storefront-blue.svg\n/media/seed/pharmacies/interior.svg', 10.802743, 106.707209),
    (9106, 'Long Chau - Thu Duc', '102 Kha Van Can, Linh Chieu, Thu Duc, TP.HCM', '02839210006', '07:00 - 22:00', 'Chi nhanh phuc vu sinh vien va ho gia dinh o khu Dong.', 'seed/pharmacies/storefront-green.svg', E'/media/seed/pharmacies/storefront-green.svg\n/media/seed/pharmacies/interior.svg', 10.849679, 106.761522),
    (9107, 'CareOne - Tan Binh', '350 Hoang Van Thu, Phuong 4, Tan Binh, TP.HCM', '02839210007', '07:00 - 22:00', 'Chi nhanh gan san bay, phu hop don giao khan.', 'seed/pharmacies/storefront-blue.svg', E'/media/seed/pharmacies/storefront-blue.svg\n/media/seed/pharmacies/interior.svg', 10.800732, 106.664728),
    (9108, 'Suc Khoe Viet - Phu Nhuan', '212 Nguyen Kiem, Phuong 7, Phu Nhuan, TP.HCM', '02839210008', '07:00 - 22:00', 'Chi nhanh duoc chon nhieu cho don gia dinh va me be.', 'seed/pharmacies/storefront-green.svg', E'/media/seed/pharmacies/storefront-green.svg\n/media/seed/pharmacies/interior.svg', 10.800122, 106.680734),
    (9109, 'An Tam - Binh Tan', '602 Kinh Duong Vuong, An Lac, Binh Tan, TP.HCM', '02839210009', '07:00 - 22:00', 'Chi nhanh bao phu khu Tay Sai Gon voi ton kho on dinh.', 'seed/pharmacies/storefront-blue.svg', E'/media/seed/pharmacies/storefront-blue.svg\n/media/seed/pharmacies/interior.svg', 10.739942, 106.615298),
    (9110, 'Family Pharma - Quan 7', '341 Huynh Tan Phat, Tan Thuan Dong, Quan 7, TP.HCM', '02839210010', '07:00 - 22:00', 'Chi nhanh linh hoat cho khu dan cu moi va chung cu.', 'seed/pharmacies/storefront-green.svg', E'/media/seed/pharmacies/storefront-green.svg\n/media/seed/pharmacies/interior.svg', 10.742113, 106.734560),
    (9111, 'Dong Nam Pharmacy - Tan Phu', '415 Luy Ban Bich, Hiep Tan, Tan Phu, TP.HCM', '02839210011', '07:00 - 22:00', 'Chi nhanh co nhieu mat hang tieu hoa, ho hap va thuoc thong dung.', 'seed/pharmacies/storefront-blue.svg', E'/media/seed/pharmacies/storefront-blue.svg\n/media/seed/pharmacies/interior.svg', 10.767556, 106.628912),
    (9112, 'City Drugstore - Quan 5', '51 Nguyen Trai, Phuong 2, Quan 5, TP.HCM', '02839210012', '07:00 - 22:30', 'Chi nhanh trung tam khu Tay, phu hop don giao hang nhanh.', 'seed/pharmacies/storefront-green.svg', E'/media/seed/pharmacies/storefront-green.svg\n/media/seed/pharmacies/interior.svg', 10.758497, 106.677987);

WITH pharmacy_seed AS (
    SELECT *
    FROM (
        VALUES
            (1, 9101), (2, 9102), (3, 9103), (4, 9104), (5, 9105), (6, 9106),
            (7, 9107), (8, 9108), (9, 9109), (10, 9110), (11, 9111), (12, 9112)
    ) AS p(seq, pharmacy_id)
),
medicine_catalog AS (
    SELECT *
    FROM (
        VALUES
            (1, 'Paracetamol 500mg',      'Giam dau - ha sot',      'Hop',  'DHG Pharma',        'Viet Nam',  32000, E'/media/seed/medicines/paracetamol.svg',  'Thuoc thong dung ho tro giam dau va ha sot cho gia dinh.', 'Giam dau, ha sot, dau dau, nhuc co.', 'Paracetamol 500mg', 'Uong sau an, 1 vien moi 4-6 gio khi can.', FALSE),
            (2, 'Vitamin C 1000mg',       'Vitamin - khoang chat',  'Hop',  'Hasan',             'Viet Nam',  69000, E'/media/seed/medicines/vitamin-c.svg',    'Bo sung vitamin C tang de khang va phuc hoi suc khoe.', 'Bo sung vitamin C, giam met moi.', 'Vitamin C 1000mg, keo ong', 'Dung 1 vien/ngay sau bua sang.', FALSE),
            (3, 'Amoxicillin 500mg',      'Khang sinh',             'Hop',  'Imexpharm',         'Viet Nam', 118000, E'/media/seed/medicines/amoxicillin.svg', 'Khang sinh duoc dung theo chi dinh bac si.', 'Dieu tri nhiem khuan duong ho hap va tai mui hong.', 'Amoxicillin 500mg', 'Su dung theo don va huong dan chuyen mon.', TRUE),
            (4, 'Oresol Bu Nuoc',         'Tieu hoa',               'Hop',  'Traphaco',          'Viet Nam',  25000, E'/media/seed/medicines/oresol.svg',      'Bo sung nuoc va dien giai cho nguoi bi mat nuoc.', 'Bu nuoc khi tieu chay, sot, van dong nhieu.', 'Muoi khoang va glucose', 'Pha dung ti le huong dan tren bao bi.', FALSE),
            (5, 'Cetirizin 10mg',         'Di ung - ho hap',        'Hop',  'Pymepharco',        'Viet Nam',  42000, E'/media/seed/medicines/cetirizin.svg',   'Thuoc giam trieu chung viem mui di ung va me day.', 'Giam hat hoi, chay mui, ngua da.', 'Cetirizin hydroclorid 10mg', 'Dung 1 vien vao buoi toi.', FALSE),
            (6, 'Omeprazole 20mg',        'Da day - tieu hoa',      'Hop',  'Boston Pharma',     'Viet Nam',  76000, E'/media/seed/medicines/omeprazole.svg',  'Ho tro giam tiet acid da day va trao nguoc.', 'Ho tro viem da day, trao nguoc, non nao.', 'Omeprazole 20mg', 'Dung truoc bua sang 30 phut.', FALSE),
            (7, 'Siro Ho Thao Duoc',      'Ho - cam',               'Chai', 'Duoc Hau Giang',    'Viet Nam',  58000, E'/media/seed/medicines/siro-ho.svg',     'Siro ho thao duoc phu hop cho nguoi lon va tre em tren 6 tuoi.', 'Lam diu hong, giam ho, giam rat hong.', 'Mat ong, hung chanh, tinh dau khuynh diep', 'Dung 10ml moi lan, ngay 2-3 lan.', FALSE),
            (8, 'Nuoc Muoi Sinh Ly 0.9%', 'Cham soc co ban',        'Chai', 'Vinh Phuc Medical', 'Viet Nam',  18000, E'/media/seed/medicines/nuoc-muoi.svg',  'Dung de rua mui, mat va ve sinh hang ngay.', 'Ve sinh mui hong, lam sach vet thuong nho.', 'NaCl 0.9%', 'Dung truc tiep theo nhu cau.', FALSE)
    ) AS c(seq, name, category, unit, manufacturer, origin, base_price, gallery_urls, description, usage, ingredients, dosage, prescription_required)
)
INSERT INTO myapp_medicine (
    id, pharmacy_id, name, category, unit, manufacturer, origin, price, quantity,
    image, gallery_urls, description, usage, ingredients, dosage, prescription_required
)
SELECT
    9200 + ((p.seq - 1) * 8) + c.seq AS id,
    p.pharmacy_id,
    c.name,
    c.category,
    c.unit,
    c.manufacturer,
    c.origin,
    c.base_price AS price,
    CASE
        WHEN c.seq = 3 AND p.seq IN (2, 5, 9) THEN 0
        WHEN c.seq = 7 AND p.seq IN (1, 4, 8, 12) THEN 5
        WHEN c.seq = 6 AND p.seq IN (3, 6, 10) THEN 8
        ELSE 18 + ((p.seq * 7 + c.seq * 3) % 46)
    END AS quantity,
    regexp_replace(split_part(c.gallery_urls, E'\n', 1), '^/media/', ''),
    c.gallery_urls,
    c.description,
    c.usage,
    c.ingredients,
    c.dosage,
    c.prescription_required
FROM pharmacy_seed p
CROSS JOIN medicine_catalog c
ORDER BY p.seq, c.seq;

INSERT INTO myapp_cart (id, user_id, session_key, created_at) VALUES
    (9301, 9004, NULL, '2026-03-25 09:00:00+07'),
    (9302, 9005, NULL, '2026-03-25 09:15:00+07'),
    (9303, 9008, NULL, '2026-03-25 09:30:00+07');

INSERT INTO myapp_cartitem (id, cart_id, medicine_id, quantity) VALUES
    (9351, 9301, 9201, 2),
    (9352, 9301, 9205, 1),
    (9353, 9302, 9209, 1),
    (9354, 9302, 9212, 2),
    (9355, 9303, 9242, 1),
    (9356, 9303, 9247, 2);

WITH order_seed AS (
    SELECT *
    FROM (
        VALUES
            (9401, 9004, 'Nguyen Thi Anh', '0901234567', '12 Nguyen Hue, Ben Nghe, Quan 1, TP.HCM', 'Giao gio hanh chinh', 10.773255, 106.704777, 9101, 4.2, 18000, 'completed', '2026-03-20 09:15:00+07'::timestamptz, ARRAY[9201,9205]::bigint[], ARRAY[2,1]::integer[]),
            (9402, 9005, 'Pham Quoc Binh', '0902345678', '44 Le Van Sy, Phuong 14, Quan 3, TP.HCM', 'Khong goi cua sau 21h', 10.786564, 106.678626, 9102, 2.8, 15000, 'shipping',  '2026-03-21 10:10:00+07'::timestamptz, ARRAY[9209,9213,9214]::bigint[], ARRAY[1,2,1]::integer[]),
            (9403, 9006, 'Vo Thi Lan', '0903456789', '211 Au Co, Phuong 5, Quan 11, TP.HCM', '', 10.764893, 106.648717, 9103, 5.4, 22000, 'completed', '2026-03-21 14:45:00+07'::timestamptz, ARRAY[9217,9221]::bigint[], ARRAY[1,2]::integer[]),
            (9404, 9007, 'Do Minh Tam', '0904567890', '88 Nguyen Xi, Phuong 26, Binh Thanh, TP.HCM', 'Nhan hang tai bao ve', 10.812647, 106.709027, 9105, 3.1, 17000, 'pending',  '2026-03-22 08:20:00+07'::timestamptz, ARRAY[9233,9238]::bigint[], ARRAY[1,3]::integer[]),
            (9405, 9008, 'Tran Ngoc Ha', '0905678901', '102 Kha Van Can, Linh Chieu, Thu Duc, TP.HCM', '', 10.849679, 106.761522, 9106, 1.6, 12000, 'completed', '2026-03-22 11:05:00+07'::timestamptz, ARRAY[9241,9248]::bigint[], ARRAY[2,2]::integer[]),
            (9406, 9009, 'Le Hoang Phuc', '0906789012', '341 Huynh Tan Phat, Tan Thuan Dong, Quan 7, TP.HCM', 'Nhan tai sanh chung cu', 10.742113, 106.734560, 9110, 2.2, 14000, 'shipping',  '2026-03-22 17:40:00+07'::timestamptz, ARRAY[9273,9275,9278]::bigint[], ARRAY[1,1,2]::integer[]),
            (9407, 9010, 'Hoang Bao Tram', '0907890123', '145 Lu Gia, Phuong 15, Quan 11, TP.HCM', '', 10.767662, 106.657854, 9103, 3.9, 18000, 'cancelled', '2026-03-23 09:30:00+07'::timestamptz, ARRAY[9218,9223]::bigint[], ARRAY[1,1]::integer[]),
            (9408, 9004, 'Nguyen Thi Anh', '0901234567', '12 Nguyen Hue, Ben Nghe, Quan 1, TP.HCM', 'Giao cuoi gio chieu', 10.773255, 106.704777, 9101, 4.4, 19000, 'completed', '2026-03-23 16:10:00+07'::timestamptz, ARRAY[9202,9204,9208]::bigint[], ARRAY[1,1,3]::integer[]),
            (9409, 9005, 'Pham Quoc Binh', '0902345678', '44 Le Van Sy, Phuong 14, Quan 3, TP.HCM', '', 10.786564, 106.678626, 9102, 2.4, 14000, 'completed', '2026-03-24 09:05:00+07'::timestamptz, ARRAY[9210,9215]::bigint[], ARRAY[2,1]::integer[]),
            (9410, 9007, 'Do Minh Tam', '0904567890', '88 Nguyen Xi, Phuong 26, Binh Thanh, TP.HCM', 'Lien he truoc 10 phut', 10.812647, 106.709027, 9105, 2.7, 15000, 'pending',  '2026-03-24 15:30:00+07'::timestamptz, ARRAY[9234,9236,9237]::bigint[], ARRAY[1,1,1]::integer[]),
            (9411, 9008, 'Tran Ngoc Ha', '0905678901', '102 Kha Van Can, Linh Chieu, Thu Duc, TP.HCM', '', 10.849679, 106.761522, 9106, 1.8, 12000, 'shipping',  '2026-03-25 08:50:00+07'::timestamptz, ARRAY[9242,9245]::bigint[], ARRAY[1,2]::integer[]),
            (9412, 9009, 'Le Hoang Phuc', '0906789012', '341 Huynh Tan Phat, Tan Thuan Dong, Quan 7, TP.HCM', 'Giao trong gio trua', 10.742113, 106.734560, 9110, 2.9, 15000, 'completed', '2026-03-25 13:20:00+07'::timestamptz, ARRAY[9274,9277,9280]::bigint[], ARRAY[2,1,1]::integer[])
    ) AS s(order_id, user_id, full_name, phone, address_text, note, delivery_lat, delivery_lng, pharmacy_id, distance_km, shipping_fee, status, created_at, medicine_ids, quantities)
),
order_totals AS (
    SELECT
        o.order_id,
        o.user_id,
        o.full_name,
        o.phone,
        o.address_text,
        o.note,
        o.delivery_lat,
        o.delivery_lng,
        o.pharmacy_id,
        o.distance_km,
        o.shipping_fee,
        o.status,
        o.created_at,
        SUM(m.price * items.quantity) AS total_product_price
    FROM order_seed o
    JOIN LATERAL unnest(o.medicine_ids, o.quantities) AS items(medicine_id, quantity) ON TRUE
    JOIN myapp_medicine m ON m.id = items.medicine_id
    GROUP BY
        o.order_id, o.user_id, o.full_name, o.phone, o.address_text, o.note,
        o.delivery_lat, o.delivery_lng, o.pharmacy_id, o.distance_km, o.shipping_fee,
        o.status, o.created_at
)
INSERT INTO myapp_order (
    id, user_id, full_name, phone, address_text, note, delivery_lat, delivery_lng,
    pharmacy_id, distance_km, shipping_fee, total_product_price, final_total_price,
    status, created_at
)
SELECT
    order_id,
    user_id,
    full_name,
    phone,
    address_text,
    note,
    delivery_lat,
    delivery_lng,
    pharmacy_id,
    distance_km,
    shipping_fee,
    total_product_price,
    total_product_price + shipping_fee,
    status,
    created_at
FROM order_totals
ORDER BY order_id;

WITH order_seed AS (
    SELECT *
    FROM (
        VALUES
            (9401, ARRAY[9201,9205]::bigint[], ARRAY[2,1]::integer[]),
            (9402, ARRAY[9209,9213,9214]::bigint[], ARRAY[1,2,1]::integer[]),
            (9403, ARRAY[9217,9221]::bigint[], ARRAY[1,2]::integer[]),
            (9404, ARRAY[9233,9238]::bigint[], ARRAY[1,3]::integer[]),
            (9405, ARRAY[9241,9248]::bigint[], ARRAY[2,2]::integer[]),
            (9406, ARRAY[9273,9275,9278]::bigint[], ARRAY[1,1,2]::integer[]),
            (9407, ARRAY[9218,9223]::bigint[], ARRAY[1,1]::integer[]),
            (9408, ARRAY[9202,9204,9208]::bigint[], ARRAY[1,1,3]::integer[]),
            (9409, ARRAY[9210,9215]::bigint[], ARRAY[2,1]::integer[]),
            (9410, ARRAY[9234,9236,9237]::bigint[], ARRAY[1,1,1]::integer[]),
            (9411, ARRAY[9242,9245]::bigint[], ARRAY[1,2]::integer[]),
            (9412, ARRAY[9274,9277,9280]::bigint[], ARRAY[2,1,1]::integer[])
    ) AS s(order_id, medicine_ids, quantities)
)
INSERT INTO myapp_orderitem (id, order_id, medicine_id, medicine_name, price, quantity)
SELECT
    9500 + ROW_NUMBER() OVER (ORDER BY o.order_id, items.ord) AS id,
    o.order_id,
    m.id,
    m.name,
    m.price,
    items.quantity
FROM order_seed o
JOIN LATERAL unnest(o.medicine_ids, o.quantities) WITH ORDINALITY AS items(medicine_id, quantity, ord) ON TRUE
JOIN myapp_medicine m ON m.id = items.medicine_id
ORDER BY o.order_id, items.ord;

SELECT setval(pg_get_serial_sequence('auth_user', 'id'), COALESCE((SELECT MAX(id) FROM auth_user), 1));
SELECT setval(pg_get_serial_sequence('myapp_userprofile', 'id'), COALESCE((SELECT MAX(id) FROM myapp_userprofile), 1));
SELECT setval(pg_get_serial_sequence('myapp_pharmacy', 'id'), COALESCE((SELECT MAX(id) FROM myapp_pharmacy), 1));
SELECT setval(pg_get_serial_sequence('myapp_medicine', 'id'), COALESCE((SELECT MAX(id) FROM myapp_medicine), 1));
SELECT setval(pg_get_serial_sequence('myapp_cart', 'id'), COALESCE((SELECT MAX(id) FROM myapp_cart), 1));
SELECT setval(pg_get_serial_sequence('myapp_cartitem', 'id'), COALESCE((SELECT MAX(id) FROM myapp_cartitem), 1));
SELECT setval(pg_get_serial_sequence('myapp_order', 'id'), COALESCE((SELECT MAX(id) FROM myapp_order), 1));
SELECT setval(pg_get_serial_sequence('myapp_orderitem', 'id'), COALESCE((SELECT MAX(id) FROM myapp_orderitem), 1));

COMMIT;
