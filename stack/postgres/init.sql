-- Initialize usage_stats database schema

CREATE TABLE IF NOT EXISTS usage_stats (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL,
    application TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on application for faster queries
CREATE INDEX IF NOT EXISTS idx_usage_stats_application ON usage_stats(application);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_usage_stats_created_at ON usage_stats(created_at);

-- Create GIN index on JSONB data for efficient JSON queries
CREATE INDEX IF NOT EXISTS idx_usage_stats_data ON usage_stats USING GIN (data);
