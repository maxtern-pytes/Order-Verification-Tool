-- Complete Migration: Add all missing columns to orders table
-- Run this SQL directly on your Supabase database

-- Add email column
ALTER TABLE orders ADD COLUMN IF NOT EXISTS email TEXT;

-- Add payment_method column
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method TEXT DEFAULT 'Prepaid';

-- Add rto_risk column
ALTER TABLE orders ADD COLUMN IF NOT EXISTS rto_risk TEXT DEFAULT 'LOW';

-- Verify columns were added
SELECT column_name, data_type, column_default
FROM information_schema.columns 
WHERE table_name = 'orders' 
ORDER BY ordinal_position;
