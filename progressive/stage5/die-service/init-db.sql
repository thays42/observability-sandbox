-- Initialize database schema for die specifications
-- This script runs automatically when the PostgreSQL container starts

-- Create the die_specifications table
CREATE TABLE IF NOT EXISTS die_specifications (
    identifier VARCHAR(50) PRIMARY KEY,
    faces INTEGER[] NOT NULL,
    error_rate FLOAT NOT NULL CHECK (error_rate >= 0 AND error_rate <= 1)
);

-- Seed the table with initial die specifications
INSERT INTO die_specifications (identifier, faces, error_rate) VALUES
    ('fair', ARRAY[1, 2, 3, 4, 5, 6], 0.0),
    ('risky', ARRAY[2, 3, 4, 5, 6, 7], 0.1),
    ('extreme', ARRAY[0, 0, 6, 6, 6, 6], 0.5)
ON CONFLICT (identifier) DO NOTHING;

-- Create an index on identifier for faster lookups (though it's already the primary key)
-- This is just to demonstrate good practices
CREATE INDEX IF NOT EXISTS idx_die_identifier ON die_specifications(identifier);

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully with % die specifications', (SELECT COUNT(*) FROM die_specifications);
END $$;
