BEGIN;

SET TIME ZONE 'Asia/Ho_Chi_Minh';

WITH catalog(name, unit, manufacturer, origin, base_price) AS (
    VALUES
        ('Paracetamol 500mg',      'Hop',  'DHG Pharma',        'Viet Nam',  32000),
        ('Vitamin C 1000mg',       'Hop',  'Hasan',             'Viet Nam',  69000),
        ('Amoxicillin 500mg',      'Hop',  'Imexpharm',         'Viet Nam', 118000),
        ('Oresol Bu Nuoc',         'Hop',  'Traphaco',          'Viet Nam',  25000),
        ('Cetirizin 10mg',         'Hop',  'Pymepharco',        'Viet Nam',  42000),
        ('Omeprazole 20mg',        'Hop',  'Boston Pharma',     'Viet Nam',  76000),
        ('Siro Ho Thao Duoc',      'Chai', 'Duoc Hau Giang',    'Viet Nam',  58000),
        ('Nuoc Muoi Sinh Ly 0.9%', 'Chai', 'Vinh Phuc Medical', 'Viet Nam',  18000)
)
UPDATE myapp_medicine AS m
SET price = c.base_price
FROM catalog AS c
WHERE lower(trim(m.name)) = lower(trim(c.name))
  AND lower(trim(m.unit)) = lower(trim(c.unit))
  AND lower(trim(coalesce(m.manufacturer, ''))) = lower(trim(c.manufacturer))
  AND lower(trim(coalesce(m.origin, ''))) = lower(trim(c.origin));

UPDATE myapp_orderitem AS oi
SET price = m.price
FROM myapp_medicine AS m
WHERE oi.medicine_id = m.id;

WITH order_totals AS (
    SELECT
        oi.order_id,
        SUM(oi.price * oi.quantity) AS total_product_price
    FROM myapp_orderitem AS oi
    GROUP BY oi.order_id
)
UPDATE myapp_order AS o
SET total_product_price = totals.total_product_price,
    final_total_price = totals.total_product_price + COALESCE(o.shipping_fee, 0)
FROM order_totals AS totals
WHERE o.id = totals.order_id;

COMMIT;
