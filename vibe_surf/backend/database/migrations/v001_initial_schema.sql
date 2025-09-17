-- Migration: v001_initial_schema.sql
-- Description: Initial database schema creation
-- Version: 0.0.1

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Create LLM Profiles table
CREATE TABLE IF NOT EXISTS llm_profiles (
    profile_id VARCHAR(36) NOT NULL PRIMARY KEY,
    profile_name VARCHAR(100) NOT NULL UNIQUE,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    base_url VARCHAR(500),
    encrypted_api_key TEXT,
    temperature JSON,
    max_tokens JSON,
    top_p JSON,
    frequency_penalty JSON,
    seed JSON,
    provider_config JSON,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_default BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME
);

-- Create Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(36) NOT NULL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    task_description TEXT NOT NULL,
    status VARCHAR(9) NOT NULL DEFAULT 'pending',
    llm_profile_name VARCHAR(100) NOT NULL,
    upload_files_path VARCHAR(500),
    workspace_dir VARCHAR(500),
    mcp_server_config TEXT,
    task_result TEXT,
    error_message TEXT,
    report_path VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME,
    task_metadata JSON,
    CHECK (status IN ('pending', 'running', 'paused', 'completed', 'failed', 'stopped'))
);

-- Create Uploaded Files table
CREATE TABLE IF NOT EXISTS uploaded_files (
    file_id VARCHAR(36) NOT NULL PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    session_id VARCHAR(255),
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    upload_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    relative_path TEXT NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT 0,
    deleted_at DATETIME
);

-- Create MCP Profiles table
CREATE TABLE IF NOT EXISTS mcp_profiles (
    mcp_id VARCHAR(36) NOT NULL PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL UNIQUE,
    mcp_server_name VARCHAR(100) NOT NULL UNIQUE,
    mcp_server_params JSON NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_llm_profiles_name ON llm_profiles(profile_name);
CREATE INDEX IF NOT EXISTS idx_llm_profiles_active ON llm_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_llm_profiles_default ON llm_profiles(is_default);
CREATE INDEX IF NOT EXISTS idx_llm_profiles_provider ON llm_profiles(provider);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_llm_profile ON tasks(llm_profile_name);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_session_time ON uploaded_files(session_id, upload_time);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_active ON uploaded_files(is_deleted, upload_time);
CREATE INDEX IF NOT EXISTS idx_uploaded_files_filename ON uploaded_files(original_filename);

CREATE INDEX IF NOT EXISTS idx_mcp_profiles_display_name ON mcp_profiles(display_name);
CREATE INDEX IF NOT EXISTS idx_mcp_profiles_server_name ON mcp_profiles(mcp_server_name);
CREATE INDEX IF NOT EXISTS idx_mcp_profiles_active ON mcp_profiles(is_active);

-- Create triggers for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_llm_profiles_updated_at
AFTER UPDATE ON llm_profiles
FOR EACH ROW
BEGIN
    UPDATE llm_profiles SET updated_at = CURRENT_TIMESTAMP WHERE profile_id = OLD.profile_id;
END;

CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at
AFTER UPDATE ON tasks
FOR EACH ROW
BEGIN
    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE task_id = OLD.task_id;
END;

CREATE TRIGGER IF NOT EXISTS update_mcp_profiles_updated_at
AFTER UPDATE ON mcp_profiles
FOR EACH ROW
BEGIN
    UPDATE mcp_profiles SET updated_at = CURRENT_TIMESTAMP WHERE mcp_id = OLD.mcp_id;
END;