-- SmartBOQ Pro — PostgreSQL initialization
-- Runs once on first container startup via docker-entrypoint-initdb.d

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for fast ILIKE searches

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE smartboq TO smartboq_user;
