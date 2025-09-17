-- Migration: v002_add_agent_mode.sql
-- Description: Add agent_mode column to tasks table
-- Version: 0.0.2

-- Add agent_mode column to tasks table with default value 'thinking'
ALTER TABLE tasks ADD COLUMN agent_mode VARCHAR(50) DEFAULT 'thinking';