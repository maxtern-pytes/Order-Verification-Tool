-- Debug script: Check what the total column actually contains
-- Run this to see the actual data format

SELECT 
    id,
    customer_name,
    phone,
    total,
    status,
    -- Try different parsing methods
    REGEXP_REPLACE(total, '[^0-9.]', '', 'g') as cleaned_total,
    CAST(NULLIF(REGEXP_REPLACE(total, '[^0-9.]', '', 'g'), '') AS DECIMAL(10,2)) as parsed_total
FROM orders
WHERE status = 'Confirmed'
LIMIT 10;

-- Also check if there are any confirmed orders at all
SELECT 
    COUNT(*) as total_orders,
    COUNT(*) FILTER (WHERE status = 'Confirmed') as confirmed_orders,
    COUNT(*) FILTER (WHERE total IS NOT NULL AND total != '') as orders_with_total
FROM orders;
