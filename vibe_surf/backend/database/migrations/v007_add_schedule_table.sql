-- Migration v007: Add schedule table for workflow scheduling
-- Created: 2025-10-21

CREATE TABLE IF NOT EXISTS schedules (
    id VARCHAR(36) PRIMARY KEY,
    flow_id VARCHAR(36) NOT NULL UNIQUE,
    cron_expression VARCHAR(100),
    is_enabled BOOLEAN NOT NULL DEFAULT 1,
    description TEXT,
    last_execution_at DATETIME,
    next_execution_at DATETIME,
    execution_count BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_schedules_flow_id ON schedules(flow_id);
CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(is_enabled);
CREATE INDEX IF NOT EXISTS idx_schedules_next_execution ON schedules(next_execution_at);
CREATE INDEX IF NOT EXISTS idx_schedules_cron ON schedules(cron_expression);

-- Add a trigger to update the updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_schedules_updated_at
    AFTER UPDATE ON schedules
    FOR EACH ROW
    BEGIN
        UPDATE schedules SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;