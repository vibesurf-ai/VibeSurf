-- Migration: v003_fix_task_status_case.sql
-- Description: Fix task status values to use lowercase (enum values)
-- Version: 0.0.3

-- Update any uppercase status values to lowercase to match TaskStatus enum
UPDATE tasks SET status = 'pending' WHERE status = 'PENDING';
UPDATE tasks SET status = 'running' WHERE status = 'RUNNING';
UPDATE tasks SET status = 'paused' WHERE status = 'PAUSED';
UPDATE tasks SET status = 'completed' WHERE status = 'COMPLETED';
UPDATE tasks SET status = 'failed' WHERE status = 'FAILED';
UPDATE tasks SET status = 'stopped' WHERE status = 'STOPPED';