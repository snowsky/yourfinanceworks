-- Initialize master database for multi-tenant invoice app
-- This script runs when the PostgreSQL container starts

-- Create the master database if it doesn't exist
SELECT 'CREATE DATABASE invoice_master'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'invoice_master')\gexec

-- Connect to the master database
\c invoice_master;

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the tenants table with all required columns
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    subdomain VARCHAR(255) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Company details
    email VARCHAR(255),
    phone VARCHAR(255),
    address TEXT,
    tax_id VARCHAR(255),
    company_logo_url VARCHAR(255),
    enable_ai_assistant BOOLEAN DEFAULT FALSE,
    
    -- Currency settings
    default_currency VARCHAR(10) DEFAULT 'USD' NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create the master_users table with all required columns
CREATE TABLE IF NOT EXISTS master_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_superuser BOOLEAN DEFAULT FALSE NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE NOT NULL,
    theme VARCHAR(50) DEFAULT 'system',
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    google_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tenants_subdomain ON tenants(subdomain);
CREATE INDEX IF NOT EXISTS idx_master_users_email ON master_users(email);
CREATE INDEX IF NOT EXISTS idx_master_users_tenant_id ON master_users(tenant_id);
