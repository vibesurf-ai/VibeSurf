-- Migration: v004_add_voice_profiles.sql
-- Description: Add voice_profiles table for voice model management
-- Version: 0.0.4

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Create Voice Profiles table
CREATE TABLE IF NOT EXISTS voice_profiles (
    profile_id VARCHAR(36) NOT NULL PRIMARY KEY,
    voice_profile_name VARCHAR(100) NOT NULL UNIQUE,
    voice_model_type VARCHAR(3) NOT NULL,
    voice_model_name VARCHAR(100) NOT NULL,
    encrypted_api_key TEXT,
    voice_meta_params JSON,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME,
    CHECK (voice_model_type IN ('asr', 'tts'))
);

-- Create indexes for voice profiles
CREATE INDEX IF NOT EXISTS idx_voice_profiles_name ON voice_profiles(voice_profile_name);
CREATE INDEX IF NOT EXISTS idx_voice_profiles_type ON voice_profiles(voice_model_type);
CREATE INDEX IF NOT EXISTS idx_voice_profiles_active ON voice_profiles(is_active);

-- Create trigger for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_voice_profiles_updated_at
AFTER UPDATE ON voice_profiles
FOR EACH ROW
BEGIN
    UPDATE voice_profiles SET updated_at = CURRENT_TIMESTAMP WHERE profile_id = OLD.profile_id;
END;