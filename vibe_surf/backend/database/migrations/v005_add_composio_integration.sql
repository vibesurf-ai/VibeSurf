-- Migration: v005_add_composio_integration.sql
-- Description: Add composio_toolkits table for Composio integration management
-- Version: 0.0.5

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Create Composio Toolkits table
CREATE TABLE IF NOT EXISTS composio_toolkits (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    logo TEXT,
    app_url TEXT,
    enabled BOOLEAN NOT NULL DEFAULT 0,
    tools TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for composio_toolkits
CREATE INDEX IF NOT EXISTS idx_composio_toolkits_name ON composio_toolkits(name);
CREATE INDEX IF NOT EXISTS idx_composio_toolkits_slug ON composio_toolkits(slug);
CREATE INDEX IF NOT EXISTS idx_composio_toolkits_enabled ON composio_toolkits(enabled);

-- Create trigger for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_composio_toolkits_updated_at
AFTER UPDATE ON composio_toolkits
FOR EACH ROW
BEGIN
    UPDATE composio_toolkits SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;