-- Migration v008: Add workflow_skills table for skill configuration
-- Created: 2025-12-14

CREATE TABLE IF NOT EXISTS workflow_skills (
    id VARCHAR(36) PRIMARY KEY,
    flow_id VARCHAR(36) NOT NULL UNIQUE,
    name VARCHAR(255),
    description TEXT,
    add_to_skill BOOLEAN NOT NULL DEFAULT 0,
    workflow_expose_config TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_workflow_skills_flow_id ON workflow_skills(flow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_skills_enabled ON workflow_skills(add_to_skill);

-- Add a trigger to update the updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_workflow_skills_updated_at
    AFTER UPDATE ON workflow_skills
    FOR EACH ROW
    BEGIN
        UPDATE workflow_skills SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;