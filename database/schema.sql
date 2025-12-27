-- PostgreSQL Database Schema for Enterprise LLM SaaS
-- Version: 1.0
-- Description: Multi-tenant RAG application with authentication, ACL, and audit logging

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. TENANTS (Organizations)
-- ============================================
CREATE TABLE tenants (
    tenant_id VARCHAR(255) PRIMARY KEY,
    tenant_name VARCHAR(255) NOT NULL,
    tier VARCHAR(50) NOT NULL DEFAULT 'standard', -- free, standard, enterprise, dedicated
    deployment_mode VARCHAR(50) NOT NULL DEFAULT 'multi_tenant', -- multi_tenant, single_tenant

    -- Feature flags
    custom_model_allowed BOOLEAN DEFAULT FALSE,
    advanced_security BOOLEAN DEFAULT FALSE,
    sso_enabled BOOLEAN DEFAULT FALSE,

    -- Resource limits
    max_users INTEGER,
    max_documents INTEGER,
    max_storage_gb INTEGER,
    api_rate_limit INTEGER NOT NULL DEFAULT 100,

    -- URLs
    dedicated_instance_url VARCHAR(512),

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indexes
    CONSTRAINT tier_check CHECK (tier IN ('free', 'standard', 'enterprise', 'dedicated')),
    CONSTRAINT deployment_mode_check CHECK (deployment_mode IN ('multi_tenant', 'single_tenant'))
);

CREATE INDEX idx_tenants_tier ON tenants(tier);
CREATE INDEX idx_tenants_active ON tenants(is_active);

-- ============================================
-- 2. USERS
-- ============================================
CREATE TABLE users (
    user_id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,

    -- Profile
    name VARCHAR(255),
    given_name VARCHAR(255),
    family_name VARCHAR(255),
    picture VARCHAR(512),

    -- Authentication
    password_hash VARCHAR(512), -- NULL for OAuth-only users
    oauth_provider VARCHAR(50), -- google, microsoft, okta, auth0
    oauth_provider_user_id VARCHAR(255),

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,

    -- Constraints
    UNIQUE(tenant_id, email),
    UNIQUE(oauth_provider, oauth_provider_user_id)
);

CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_provider_user_id);

-- ============================================
-- 3. ROLES
-- ============================================
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_system_role BOOLEAN NOT NULL DEFAULT TRUE, -- System vs custom roles

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default roles
INSERT INTO roles (role_name, description, is_system_role) VALUES
    ('admin', 'Full access to all resources', TRUE),
    ('editor', 'Can read and write documents', TRUE),
    ('viewer', 'Read-only access', TRUE),
    ('guest', 'Limited read access', TRUE);

-- ============================================
-- 4. PERMISSIONS
-- ============================================
CREATE TABLE permissions (
    permission_id SERIAL PRIMARY KEY,
    permission_name VARCHAR(100) NOT NULL UNIQUE,
    resource_type VARCHAR(50) NOT NULL, -- documents, users, settings, analytics
    action VARCHAR(50) NOT NULL, -- read, write, delete, search
    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(resource_type, action)
);

-- Insert default permissions
INSERT INTO permissions (permission_name, resource_type, action, description) VALUES
    -- Documents
    ('read:documents', 'documents', 'read', 'Read documents'),
    ('write:documents', 'documents', 'write', 'Create and update documents'),
    ('delete:documents', 'documents', 'delete', 'Delete documents'),

    -- Search
    ('search', 'search', 'read', 'Basic search'),
    ('advanced_search', 'search', 'read', 'Advanced search with filters'),

    -- Users
    ('read:users', 'users', 'read', 'View user information'),
    ('write:users', 'users', 'write', 'Create and update users'),
    ('delete:users', 'users', 'delete', 'Delete users'),

    -- Settings
    ('read:settings', 'settings', 'read', 'View settings'),
    ('write:settings', 'settings', 'write', 'Modify settings'),

    -- Analytics
    ('read:analytics', 'analytics', 'read', 'View analytics and reports');

-- ============================================
-- 5. ROLE_PERMISSIONS (Many-to-Many)
-- ============================================
CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,

    PRIMARY KEY (role_id, permission_id)
);

-- Assign permissions to roles
-- Admin: all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_name = 'admin';

-- Editor: read/write documents, search, read users
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_name = 'editor'
  AND p.permission_name IN (
    'read:documents', 'write:documents', 'search', 'advanced_search', 'read:users'
  );

-- Viewer: read documents, basic search
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_name = 'viewer'
  AND p.permission_name IN ('read:documents', 'search');

-- Guest: read documents only
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM roles r
CROSS JOIN permissions p
WHERE r.role_name = 'guest'
  AND p.permission_name = 'read:documents';

-- ============================================
-- 6. USER_ROLES (Many-to-Many)
-- ============================================
CREATE TABLE user_roles (
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,

    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by VARCHAR(255) REFERENCES users(user_id),

    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);

-- ============================================
-- 7. USER_CUSTOM_PERMISSIONS
-- ============================================
CREATE TABLE user_custom_permissions (
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(permission_id) ON DELETE CASCADE,

    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by VARCHAR(255) REFERENCES users(user_id),

    PRIMARY KEY (user_id, permission_id)
);

-- ============================================
-- 8. DOCUMENTS
-- ============================================
CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,

    -- Document metadata
    file_path TEXT NOT NULL,
    file_name VARCHAR(512) NOT NULL,
    file_type VARCHAR(50),
    file_size_bytes BIGINT,

    -- Source information
    source_type VARCHAR(50) NOT NULL, -- filesystem, gdrive, sharepoint, s3
    source_path TEXT NOT NULL,
    source_url TEXT,

    -- Ownership
    owner_id VARCHAR(255) REFERENCES users(user_id),
    parent_folder_id UUID REFERENCES documents(document_id), -- For folder hierarchy
    is_folder BOOLEAN NOT NULL DEFAULT FALSE,

    -- Indexing status
    indexed_at TIMESTAMPTZ,
    embedding_model VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_at TIMESTAMPTZ, -- Original file modification time

    -- Metadata (JSON for flexible schema)
    metadata JSONB,

    -- Constraints
    UNIQUE(tenant_id, source_path)
);

CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_owner ON documents(owner_id);
CREATE INDEX idx_documents_parent ON documents(parent_folder_id);
CREATE INDEX idx_documents_source ON documents(source_type, source_path);
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);

-- ============================================
-- 9. DOCUMENT_PERMISSIONS (ACL)
-- ============================================
CREATE TABLE document_permissions (
    permission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    tenant_id VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,

    -- Permission target (user or role)
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES roles(role_id) ON DELETE CASCADE,

    -- Access level
    access_level VARCHAR(50) NOT NULL, -- read, write, admin, none

    -- Inheritance
    inherited_from UUID REFERENCES documents(document_id), -- If inherited from parent folder
    is_inherited BOOLEAN NOT NULL DEFAULT FALSE,

    -- Granted by
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by VARCHAR(255) REFERENCES users(user_id),

    -- Constraints: either user_id or role_id must be set, not both
    CONSTRAINT check_user_or_role CHECK (
        (user_id IS NOT NULL AND role_id IS NULL) OR
        (user_id IS NULL AND role_id IS NOT NULL)
    ),
    CONSTRAINT access_level_check CHECK (
        access_level IN ('read', 'write', 'admin', 'none')
    )
);

CREATE INDEX idx_document_permissions_document ON document_permissions(document_id);
CREATE INDEX idx_document_permissions_user ON document_permissions(user_id);
CREATE INDEX idx_document_permissions_role ON document_permissions(role_id);
CREATE INDEX idx_document_permissions_tenant ON document_permissions(tenant_id);

-- ============================================
-- 10. AUDIT_LOGS
-- ============================================
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,

    -- Actor
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE SET NULL,
    user_email VARCHAR(255),

    -- Action
    action VARCHAR(100) NOT NULL, -- login, logout, search, read, write, delete, etc.
    resource_type VARCHAR(50), -- document, user, setting, etc.
    resource_id VARCHAR(255),

    -- Request details
    ip_address INET,
    user_agent TEXT,
    request_method VARCHAR(10),
    request_path TEXT,

    -- Result
    status_code INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,

    -- Additional metadata
    metadata JSONB,

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_metadata ON audit_logs USING GIN (metadata);

-- ============================================
-- 11. REFRESH_TOKENS
-- ============================================
CREATE TABLE refresh_tokens (
    token_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    tenant_id VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,

    token_hash VARCHAR(512) NOT NULL, -- SHA256 hash of token

    -- Status
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT,

    -- Metadata
    ip_address INET,
    user_agent TEXT,

    -- Expiration
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,

    UNIQUE(token_hash)
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);

-- ============================================
-- 12. SEARCH_QUERIES (for analytics)
-- ============================================
CREATE TABLE search_queries (
    query_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id VARCHAR(255) REFERENCES users(user_id) ON DELETE SET NULL,

    -- Query
    query_text TEXT NOT NULL,
    query_type VARCHAR(50) NOT NULL DEFAULT 'search', -- search, qa, summarize

    -- Results
    results_count INTEGER,
    top_document_id UUID REFERENCES documents(document_id),

    -- Performance
    response_time_ms INTEGER,

    -- Feedback
    user_rating INTEGER, -- 1-5 stars, NULL if not rated
    user_feedback TEXT,

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_queries_tenant ON search_queries(tenant_id);
CREATE INDEX idx_search_queries_user ON search_queries(user_id);
CREATE INDEX idx_search_queries_timestamp ON search_queries(timestamp DESC);

-- ============================================
-- VIEWS
-- ============================================

-- User permissions view (combines roles and custom permissions)
CREATE VIEW user_all_permissions AS
SELECT DISTINCT
    u.user_id,
    u.tenant_id,
    p.permission_id,
    p.permission_name,
    p.resource_type,
    p.action,
    'role' as source
FROM users u
JOIN user_roles ur ON u.user_id = ur.user_id
JOIN role_permissions rp ON ur.role_id = rp.role_id
JOIN permissions p ON rp.permission_id = p.permission_id
WHERE u.is_active = TRUE

UNION

SELECT DISTINCT
    u.user_id,
    u.tenant_id,
    p.permission_id,
    p.permission_name,
    p.resource_type,
    p.action,
    'custom' as source
FROM users u
JOIN user_custom_permissions ucp ON u.user_id = ucp.user_id
JOIN permissions p ON ucp.permission_id = p.permission_id
WHERE u.is_active = TRUE;

-- Document access view (who can access which documents)
CREATE VIEW document_access AS
WITH user_document_perms AS (
    -- Direct user permissions
    SELECT
        dp.document_id,
        dp.user_id,
        dp.access_level,
        'direct' as permission_type
    FROM document_permissions dp
    WHERE dp.user_id IS NOT NULL

    UNION

    -- Role-based permissions
    SELECT
        dp.document_id,
        ur.user_id,
        dp.access_level,
        'role' as permission_type
    FROM document_permissions dp
    JOIN user_roles ur ON dp.role_id = ur.role_id
    WHERE dp.role_id IS NOT NULL
)
SELECT
    d.document_id,
    d.tenant_id,
    d.file_path,
    udp.user_id,
    udp.access_level,
    udp.permission_type
FROM documents d
JOIN user_document_perms udp ON d.document_id = udp.document_id;

-- ============================================
-- FUNCTIONS
-- ============================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_tenants_updated_at BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to check user permission on document
CREATE OR REPLACE FUNCTION user_can_access_document(
    p_user_id VARCHAR,
    p_document_id UUID,
    p_required_access VARCHAR DEFAULT 'read'
)
RETURNS BOOLEAN AS $$
DECLARE
    v_has_access BOOLEAN;
BEGIN
    -- Check if user has required access level
    SELECT EXISTS (
        SELECT 1
        FROM document_access
        WHERE user_id = p_user_id
          AND document_id = p_document_id
          AND (
              (p_required_access = 'read' AND access_level IN ('read', 'write', 'admin')) OR
              (p_required_access = 'write' AND access_level IN ('write', 'admin')) OR
              (p_required_access = 'admin' AND access_level = 'admin')
          )
    ) INTO v_has_access;

    RETURN v_has_access;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- COMMENTS
-- ============================================
COMMENT ON TABLE tenants IS 'Organizations/tenants in multi-tenant architecture';
COMMENT ON TABLE users IS 'User accounts with authentication info';
COMMENT ON TABLE roles IS 'System and custom roles';
COMMENT ON TABLE permissions IS 'Granular permissions for resources';
COMMENT ON TABLE documents IS 'Indexed documents with metadata';
COMMENT ON TABLE document_permissions IS 'Access control list for documents';
COMMENT ON TABLE audit_logs IS 'Audit trail for all actions (GDPR compliance)';
COMMENT ON TABLE refresh_tokens IS 'JWT refresh tokens';
COMMENT ON TABLE search_queries IS 'Search analytics';
