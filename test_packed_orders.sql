-- Quick test script to verify packed orders feature
-- Run this in Supabase SQL editor after running migration_add_packed.sql

-- 1. Check if is_packed column exists
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'orders' AND column_name = 'is_packed';

-- 2. Count orders by packed status
SELECT 
    is_packed,
    COUNT(*) as count
FROM orders
WHERE status = 'Confirmed'
GROUP BY is_packed;

-- 3. Mark a test order as packed (replace with actual order ID)
-- UPDATE orders SET is_packed = TRUE WHERE id = 'YOUR_ORDER_ID_HERE';

-- 4. View packed orders
SELECT id, customer_name, phone, total, is_packed
FROM orders
WHERE status = 'Confirmed' AND is_packed = TRUE
LIMIT 5;

-- 5. View unpacked orders
SELECT id, customer_name, phone, total, is_packed
FROM orders
WHERE status = 'Confirmed' AND (is_packed = FALSE OR is_packed IS NULL)
LIMIT 5;
