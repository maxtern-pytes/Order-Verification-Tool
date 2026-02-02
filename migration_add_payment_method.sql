-- Migration: Add payment_method column to orders table
-- Run this SQL directly on your Supabase/Render database

ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method TEXT DEFAULT 'Prepaid';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS rto_risk TEXT DEFAULT 'LOW';

-- Update existing COD orders if any
UPDATE orders SET payment_method = 'COD' WHERE payment_method IS NULL AND source = 'Shiprocket';
