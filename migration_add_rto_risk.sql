-- Migration: Add rto_risk column to orders table
-- Run this SQL directly on your Supabase database

ALTER TABLE orders ADD COLUMN IF NOT EXISTS rto_risk TEXT DEFAULT 'LOW';

-- Update existing orders with default LOW risk
UPDATE orders SET rto_risk = 'LOW' WHERE rto_risk IS NULL;
