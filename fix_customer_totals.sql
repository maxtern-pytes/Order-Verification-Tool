-- Fix: Update customer totals to include ALL orders, not just confirmed
-- Also add a separate field for confirmed order value

-- First, add a new column for confirmed order value
ALTER TABLE customers ADD COLUMN IF NOT EXISTS confirmed_value DECIMAL(10,2) DEFAULT 0;

-- Update total_spent to include ALL orders (not just confirmed)
UPDATE customers c
SET total_spent = (
    SELECT COALESCE(SUM(CASE 
        WHEN o.total IS NOT NULL AND o.total != '' 
        THEN CAST(NULLIF(REGEXP_REPLACE(o.total, '[^0-9.]', '', 'g'), '') AS DECIMAL(10,2))
        ELSE 0 
    END), 0)
    FROM orders o
    WHERE o.phone = c.phone
);

-- Update confirmed_value to show only confirmed order value
UPDATE customers c
SET confirmed_value = (
    SELECT COALESCE(SUM(CASE 
        WHEN o.status = 'Confirmed' AND o.total IS NOT NULL AND o.total != '' 
        THEN CAST(NULLIF(REGEXP_REPLACE(o.total, '[^0-9.]', '', 'g'), '') AS DECIMAL(10,2))
        ELSE 0 
    END), 0)
    FROM orders o
    WHERE o.phone = c.phone
);

-- Update other stats
UPDATE customers c
SET 
    total_orders = (SELECT COUNT(*) FROM orders o WHERE o.phone = c.phone),
    confirmed_orders = (SELECT COUNT(*) FROM orders o WHERE o.phone = c.phone AND o.status = 'Confirmed'),
    cancelled_orders = (SELECT COUNT(*) FROM orders o WHERE o.phone = c.phone AND o.status = 'Cancelled'),
    rto_count = (SELECT COUNT(*) FROM orders o WHERE o.phone = c.phone AND o.rto_risk = 'High');

-- Update tags based on TOTAL spending (not just confirmed)
UPDATE customers
SET tags = CASE
    WHEN total_spent > 10000 THEN '["VIP", "High Value"]'
    WHEN total_orders >= 5 THEN '["Frequent Buyer"]'
    WHEN cancelled_orders > 2 THEN '["High Risk"]'
    WHEN total_orders = 1 THEN '["New Customer"]'
    WHEN confirmed_orders >= 3 THEN '["Loyal"]'
    ELSE '[]'
END;

COMMIT;
