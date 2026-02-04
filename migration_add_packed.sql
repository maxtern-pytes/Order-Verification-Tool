-- Migration: Add is_packed column to orders table
-- Purpose: Track which orders have been packed for shipping

ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_packed BOOLEAN DEFAULT FALSE;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_orders_is_packed ON orders(is_packed);

COMMIT;
