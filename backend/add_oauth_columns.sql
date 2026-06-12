-- Add OAuth profile fields to oauth_accounts table
-- Run this SQL directly against your MailMind database

ALTER TABLE oauth_accounts
ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);

ALTER TABLE oauth_accounts
ADD COLUMN IF NOT EXISTS given_name VARCHAR(128);

ALTER TABLE oauth_accounts
ADD COLUMN IF NOT EXISTS family_name VARCHAR(128);

ALTER TABLE oauth_accounts
ADD COLUMN IF NOT EXISTS picture_url TEXT;

-- Verify the columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name='oauth_accounts'
  AND column_name IN ('display_name', 'given_name', 'family_name', 'picture_url')
ORDER BY ordinal_position;
