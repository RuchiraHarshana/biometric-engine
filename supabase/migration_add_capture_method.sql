-- Run this on Supabase SQL Editor to add capture_method column
-- to the existing fingerprint_templates table.

ALTER TABLE fingerprint_templates
ADD COLUMN IF NOT EXISTS capture_method varchar(30) NOT NULL DEFAULT 'image_upload';

COMMENT ON COLUMN fingerprint_templates.capture_method IS
  'How the fingerprint was captured: image_upload, usb_scanner, laptop_scanner';
