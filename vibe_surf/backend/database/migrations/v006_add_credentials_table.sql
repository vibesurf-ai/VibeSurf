-- Migration v006: Add credentials table for storing encrypted API keys
-- Created: 2025-01-10

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Create credentials table
CREATE TABLE IF NOT EXISTS credentials (
    id VARCHAR(36) PRIMARY KEY,
    key_name VARCHAR(100) NOT NULL UNIQUE,
    encrypted_value TEXT,
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_credentials_key_name ON credentials(key_name);

-- Create trigger for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_credentials_updated_at
AFTER UPDATE ON credentials
FOR EACH ROW
BEGIN
    UPDATE credentials SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;