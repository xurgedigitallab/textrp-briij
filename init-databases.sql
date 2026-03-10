-- Create the textrp_v2 database for the API service
-- (synapse database is auto-created by POSTGRES_DB env var)
SELECT 'CREATE DATABASE briij-testing OWNER synapse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'briij-testing')\gexec
