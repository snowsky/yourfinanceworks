# TODO: Key Vault Provider & OIDC Authentication Testing

## Overview
Test the encryption system with external key vault providers and OIDC-based authentication to ensure proper integration and functionality across AWS KMS, HashiCorp Vault, Azure Key Vault, and OIDC identity providers.

## Priority: High
**Status**: Not Started  
**Estimated Effort**: 3-4 weeks  
**Dependencies**: Access to cloud provider accounts, HashiCorp Vault instance, and OIDC identity providers

---

## 🎯 Testing Objectives

### Primary Goals
- [ ] Verify encryption/decryption functionality with each key vault provider
- [ ] Test key rotation across all providers
- [ ] Validate failover and error handling scenarios
- [ ] Ensure performance meets requirements
- [ ] Confirm security best practices implementation

### Secondary Goals
- [ ] Document configuration procedures for each provider
- [ ] Create automated testing scripts
- [ ] Establish monitoring and alerting for key vault operations
- [ ] Performance benchmarking across providers
- [ ] Implement OIDC-based key derivation and access control
- [ ] Test identity-based encryption key management

---

## 🆔 OIDC-Based Key Management Testing

### Overview
OIDC (OpenID Connect) can provide identity-based key derivation and access control, enabling:
- **Identity-based encryption**: Keys derived from user/tenant identity claims
- **Dynamic key access**: Keys accessible based on JWT token claims
- **Zero-trust security**: No long-lived credentials, token-based access
- **Multi-provider support**: Works with any OIDC-compliant identity provider

### Prerequisites
- [ ] OIDC identity provider (Auth0, Okta, Azure AD, Google, Keycloak, etc.)
- [ ] OIDC application registration
- [ ] JWT token validation setup
- [ ] Identity claim mapping configuration

### OIDC Integration Approaches

#### Approach 1: Identity-Based Key Derivation
- [ ] **Concept**: Derive encryption keys from user identity claims
- [ ] **Implementation**: Use JWT `sub` (subject) + tenant claims for key derivation
- [ ] **Benefits**: No key storage needed, keys derived deterministically
- [ ] **Use Case**: User-specific data encryption

#### Approach 2: OIDC + Key Vault Authentication
- [ ] **Concept**: Use OIDC tokens to authenticate with key vaults
- [ ] **Implementation**: Exchange JWT for key vault access tokens
- [ ] **Benefits**: Leverages existing key vault infrastructure
- [ ] **Use Case**: Service-to-service authentication

#### Approach 3: Hybrid Identity + Vault Keys
- [ ] **Concept**: Use identity claims to select appropriate vault keys
- [ ] **Implementation**: Map user/tenant identity to specific key vault keys
- [ ] **Benefits**: Combines identity-based access with centralized key management
- [ ] **Use Case**: Multi-tenant applications with identity-based isolation

### Configuration Testing
- [ ] **Environment Setup**
  ```bash
  export KEY_VAULT_PROVIDER=oidc
  export OIDC_ISSUER_URL=https://your-provider.auth0.com/
  export OIDC_CLIENT_ID=your_client_id
  export OIDC_CLIENT_SECRET=your_client_secret
  export OIDC_AUDIENCE=your_api_audience
  export OIDC_KEY_DERIVATION_CLAIM=sub  # or custom claim
  export OIDC_TENANT_CLAIM=tenant_id
  ```

- [ ] **Identity Provider Configuration**
  - [ ] Configure OIDC application/client
  - [ ] Set up custom claims for tenant/key mapping
  - [ ] Configure token lifetime and refresh policies
  - [ ] Set up proper scopes and audiences

### Basic Functionality Tests
- [ ] **JWT Token Validation**
  - [ ] Token signature verification
  - [ ] Token expiration handling
  - [ ] Issuer validation
  - [ ] Audience validation

- [ ] **Identity-Based Key Derivation**
  - [ ] Key derivation from JWT claims
  - [ ] Consistent key generation for same identity
  - [ ] Different keys for different identities
  - [ ] Tenant isolation validation

- [ ] **Dynamic Key Access**
  - [ ] Token-based key retrieval
  - [ ] Claim-based access control
  - [ ] Token refresh handling
  - [ ] Revocation support

### Integration Tests
- [ ] **End-to-End OIDC Encryption**
  - [ ] User authentication via OIDC
  - [ ] Key derivation from user identity
  - [ ] Data encryption/decryption
  - [ ] Multi-user isolation

- [ ] **Tenant-Based Key Management**
  - [ ] Tenant claim extraction
  - [ ] Tenant-specific key derivation
  - [ ] Cross-tenant isolation
  - [ ] Tenant key rotation

- [ ] **Service Authentication**
  - [ ] Service-to-service OIDC authentication
  - [ ] Machine-to-machine token exchange
  - [ ] Service account key access
  - [ ] API-to-API encryption

### Error Handling Tests
- [ ] **Token Validation Errors**
  - [ ] Expired tokens
  - [ ] Invalid signatures
  - [ ] Missing claims
  - [ ] Malformed tokens

- [ ] **Identity Provider Errors**
  - [ ] OIDC provider unavailable
  - [ ] Network connectivity issues
  - [ ] Rate limiting
  - [ ] Configuration errors

- [ ] **Key Derivation Errors**
  - [ ] Missing identity claims
  - [ ] Invalid claim values
  - [ ] Key derivation failures
  - [ ] Claim mapping errors

### OIDC Provider-Specific Testing

#### Auth0 Integration
- [ ] **Configuration**
  ```bash
  export OIDC_ISSUER_URL=https://your-domain.auth0.com/
  export OIDC_CLIENT_ID=your_auth0_client_id
  export OIDC_CLIENT_SECRET=your_auth0_client_secret
  ```
- [ ] Auth0 Management API integration
- [ ] Custom claims configuration
- [ ] Rule-based claim enrichment

#### Azure AD Integration
- [ ] **Configuration**
  ```bash
  export OIDC_ISSUER_URL=https://login.microsoftonline.com/your-tenant-id/v2.0
  export OIDC_CLIENT_ID=your_azure_app_id
  export OIDC_CLIENT_SECRET=your_azure_client_secret
  ```
- [ ] Azure AD application registration
- [ ] Custom claims and optional claims
- [ ] Conditional access policies

#### Google Identity Integration
- [ ] **Configuration**
  ```bash
  export OIDC_ISSUER_URL=https://accounts.google.com
  export OIDC_CLIENT_ID=your_google_client_id
  export OIDC_CLIENT_SECRET=your_google_client_secret
  ```
- [ ] Google Cloud Identity integration
- [ ] Workspace domain claims
- [ ] Service account authentication

#### Keycloak Integration
- [ ] **Configuration**
  ```bash
  export OIDC_ISSUER_URL=https://your-keycloak.com/auth/realms/your-realm
  export OIDC_CLIENT_ID=your_keycloak_client
  export OIDC_CLIENT_SECRET=your_keycloak_secret
  ```
- [ ] Keycloak realm configuration
- [ ] Custom mappers and claims
- [ ] Role-based access control

### Advanced OIDC Features
- [ ] **Token Refresh and Rotation**
  - [ ] Automatic token refresh
  - [ ] Key re-derivation on token refresh
  - [ ] Graceful token expiration handling
  - [ ] Refresh token security

- [ ] **Multi-Factor Authentication**
  - [ ] MFA-aware key derivation
  - [ ] Step-up authentication for sensitive operations
  - [ ] MFA claim validation
  - [ ] Risk-based authentication

- [ ] **Federation and Trust**
  - [ ] Multi-provider federation
  - [ ] Trust relationship validation
  - [ ] Cross-domain authentication
  - [ ] Identity provider chaining

### Test Scripts to Create
- [ ] `test_oidc_key_derivation.py`
- [ ] `test_oidc_token_validation.py`
- [ ] `test_oidc_multi_provider.py`
- [ ] `test_oidc_tenant_isolation.py`
- [ ] `benchmark_oidc_performance.py`

---

## 🔧 AWS KMS Testing

### Prerequisites
- [ ] AWS account with KMS permissions
- [ ] IAM role/user with appropriate KMS policies
- [ ] KMS key created in target region

### Configuration Testing
- [ ] **Environment Setup**
  ```bash
  export KEY_VAULT_PROVIDER=aws_kms
  export AWS_KMS_MASTER_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
  export AWS_REGION=us-east-1
  export AWS_ACCESS_KEY_ID=your_access_key
  export AWS_SECRET_ACCESS_KEY=your_secret_key
  ```

- [ ] **Basic Functionality Tests**
  - [ ] Key creation and storage
  - [ ] Key retrieval and decryption
  - [ ] Tenant key generation
  - [ ] Master key encryption/decryption

- [ ] **Integration Tests**
  - [ ] End-to-end encryption with AWS KMS
  - [ ] OCR service with AWS KMS keys
  - [ ] Database operations with encrypted fields
  - [ ] Multi-tenant key isolation

- [ ] **Error Handling Tests**
  - [ ] Invalid AWS credentials
  - [ ] KMS key not found
  - [ ] Network connectivity issues
  - [ ] Permission denied scenarios
  - [ ] Rate limiting handling

- [ ] **Performance Tests**
  - [ ] Key retrieval latency
  - [ ] Encryption/decryption throughput
  - [ ] Concurrent operations
  - [ ] Cache effectiveness

### Test Scripts to Create
- [ ] `test_aws_kms_integration.py`
- [ ] `benchmark_aws_kms_performance.py`
- [ ] `test_aws_kms_failover.py`

---

## 🔐 HashiCorp Vault Testing

### Prerequisites
- [ ] HashiCorp Vault instance (local or cloud)
- [ ] Vault authentication token
- [ ] Transit secrets engine enabled
- [ ] Appropriate policies configured

### Configuration Testing
- [ ] **Environment Setup**
  ```bash
  export KEY_VAULT_PROVIDER=hashicorp_vault
  export HASHICORP_VAULT_URL=https://vault.example.com:8200
  export HASHICORP_VAULT_TOKEN=your_vault_token
  export HASHICORP_VAULT_NAMESPACE=your_namespace  # if using Vault Enterprise
  export HASHICORP_VAULT_MOUNT_POINT=secret
  export HASHICORP_VAULT_TRANSIT_MOUNT=transit
  ```

- [ ] **Basic Functionality Tests**
  - [ ] Vault connection and authentication
  - [ ] Transit engine key creation
  - [ ] Key encryption/decryption operations
  - [ ] Key versioning and rotation

- [ ] **Integration Tests**
  - [ ] End-to-end encryption with Vault
  - [ ] Database operations with Vault-encrypted keys
  - [ ] Multi-tenant key management
  - [ ] Key policy enforcement

- [ ] **Error Handling Tests**
  - [ ] Invalid Vault token
  - [ ] Vault server unavailable
  - [ ] Transit engine disabled
  - [ ] Policy violations
  - [ ] Token expiration handling

- [ ] **Advanced Features Tests**
  - [ ] Key versioning and rotation
  - [ ] Batch encryption operations
  - [ ] Vault namespaces (Enterprise)
  - [ ] Dynamic secrets integration

### Test Scripts to Create
- [ ] `test_hashicorp_vault_integration.py`
- [ ] `test_vault_transit_engine.py`
- [ ] `benchmark_vault_performance.py`
- [ ] `test_vault_key_rotation.py`

---

## ☁️ Azure Key Vault Testing

### Prerequisites
- [ ] Azure subscription with Key Vault access
- [ ] Service Principal or Managed Identity
- [ ] Key Vault instance created
- [ ] Appropriate access policies configured

### Configuration Testing
- [ ] **Environment Setup**
  ```bash
  export KEY_VAULT_PROVIDER=azure_keyvault
  export AZURE_KEYVAULT_URL=https://your-keyvault.vault.azure.net/
  export AZURE_CLIENT_ID=your_client_id
  export AZURE_CLIENT_SECRET=your_client_secret
  export AZURE_TENANT_ID=your_tenant_id
  ```

- [ ] **Basic Functionality Tests**
  - [ ] Azure authentication
  - [ ] Key creation and management
  - [ ] Key encryption/decryption
  - [ ] Key versioning

- [ ] **Integration Tests**
  - [ ] End-to-end encryption with Azure Key Vault
  - [ ] Database operations with Azure keys
  - [ ] Multi-tenant key isolation
  - [ ] Managed Identity authentication

- [ ] **Error Handling Tests**
  - [ ] Invalid Azure credentials
  - [ ] Key Vault access denied
  - [ ] Network connectivity issues
  - [ ] Key not found scenarios
  - [ ] Throttling handling

- [ ] **Security Tests**
  - [ ] Access policy enforcement
  - [ ] Key permissions validation
  - [ ] Audit log verification
  - [ ] Soft delete and recovery

### Test Scripts to Create
- [ ] `test_azure_keyvault_integration.py`
- [ ] `test_azure_managed_identity.py`
- [ ] `benchmark_azure_keyvault_performance.py`
- [ ] `test_azure_key_rotation.py`

---

## 🔄 Cross-Provider Testing

### Provider Switching Tests
- [ ] **Migration Testing**
  - [ ] Local to AWS KMS migration
  - [ ] Local to HashiCorp Vault migration
  - [ ] Local to Azure Key Vault migration
  - [ ] Cross-provider migrations

- [ ] **Compatibility Tests**
  - [ ] Data encrypted with one provider, decrypted with another (should fail gracefully)
  - [ ] Provider fallback mechanisms
  - [ ] Configuration validation across providers

### OIDC Integration Tests
- [ ] **OIDC + AWS KMS**
  - [ ] Use OIDC tokens to authenticate with AWS KMS
  - [ ] AWS IAM roles for OIDC federation
  - [ ] Identity-based KMS key access

- [ ] **OIDC + HashiCorp Vault**
  - [ ] Vault JWT authentication method
  - [ ] OIDC-based Vault policies
  - [ ] Dynamic secret generation based on identity

- [ ] **OIDC + Azure Key Vault**
  - [ ] Azure AD OIDC integration
  - [ ] Managed Identity with OIDC
  - [ ] Conditional access for key operations

### Test Scripts to Create
- [ ] `test_provider_migration.py`
- [ ] `test_cross_provider_compatibility.py`
- [ ] `test_provider_fallback.py`
- [ ] `test_oidc_provider_integration.py`
- [ ] `test_oidc_key_vault_federation.py`

---

## 🧪 Test Environment Setup

### Docker Compose Testing Environment
- [ ] **Create test-specific docker-compose files**
  - [ ] `docker-compose.test-aws.yml`
  - [ ] `docker-compose.test-vault.yml`
  - [ ] `docker-compose.test-azure.yml`
  - [ ] `docker-compose.test-oidc.yml`

- [ ] **Environment Configuration Files**
  - [ ] `.env.test.aws`
  - [ ] `.env.test.vault`
  - [ ] `.env.test.azure`
  - [ ] `.env.test.oidc`

### Local Development Setup
- [ ] **HashiCorp Vault Local Instance**
  ```bash
  # Create script: scripts/setup_local_vault.sh
  vault server -dev
  vault auth -method=userpass username=test password=test
  vault secrets enable transit
  ```

- [ ] **AWS LocalStack Integration**
  ```bash
  # For local AWS KMS testing
  docker run -p 4566:4566 localstack/localstack
  ```

- [ ] **Local OIDC Provider Setup**
  ```bash
  # Keycloak for local OIDC testing
  docker run -p 8080:8080 -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:latest start-dev
  
  # Or use ory/hydra for lightweight OIDC
  docker run -p 4444:4444 -p 4445:4445 oryd/hydra:latest serve all --dangerous-force-http
  ```

---

## 📊 Performance Benchmarking

### Metrics to Collect
- [ ] **Latency Metrics**
  - [ ] Key retrieval time
  - [ ] Encryption operation time
  - [ ] Decryption operation time
  - [ ] Key rotation time

- [ ] **Throughput Metrics**
  - [ ] Operations per second
  - [ ] Concurrent operation handling
  - [ ] Bulk operation performance

- [ ] **Resource Usage**
  - [ ] Memory consumption
  - [ ] CPU utilization
  - [ ] Network bandwidth

### Benchmark Scripts to Create
- [ ] `benchmark_all_providers.py`
- [ ] `performance_comparison_report.py`
- [ ] `load_test_key_operations.py`

---

## 🔍 Security Testing

### Security Validation Tests
- [ ] **Key Security**
  - [ ] Key material never exposed in logs
  - [ ] Proper key rotation procedures
  - [ ] Key access audit trails
  - [ ] Encryption at rest validation

- [ ] **Authentication & Authorization**
  - [ ] Provider authentication mechanisms
  - [ ] Permission boundary testing
  - [ ] Token/credential expiration handling
  - [ ] Multi-factor authentication support

- [ ] **Network Security**
  - [ ] TLS/SSL certificate validation
  - [ ] Network traffic encryption
  - [ ] VPC/private endpoint support
  - [ ] Firewall rule validation

### Security Test Scripts
- [ ] `test_key_security.py`
- [ ] `test_authentication_security.py`
- [ ] `test_network_security.py`
- [ ] `audit_key_operations.py`

---

## 📋 Test Execution Plan

### Phase 1: Individual Provider Testing (Week 1)
- [ ] Set up test environments for each provider
- [ ] Implement basic functionality tests
- [ ] Create configuration documentation

### Phase 2: OIDC Integration Testing (Week 2)
- [ ] Implement OIDC key derivation and authentication
- [ ] Test identity-based encryption scenarios
- [ ] OIDC provider integration testing

### Phase 3: Integration Testing (Week 3)
- [ ] End-to-end application testing with each provider
- [ ] Error handling and edge case testing
- [ ] Performance benchmarking

### Phase 4: Cross-Provider & Security Testing (Week 4)
- [ ] Provider migration testing
- [ ] OIDC federation testing
- [ ] Security validation
- [ ] Documentation and cleanup

---

## 📝 Documentation Requirements

### Configuration Guides
- [ ] **OIDC Integration Setup Guide**
  - [ ] Identity provider configuration
  - [ ] JWT token validation setup
  - [ ] Claim mapping configuration
  - [ ] Key derivation strategies
  - [ ] Multi-provider federation

- [ ] **AWS KMS Setup Guide**
  - [ ] IAM policy requirements
  - [ ] KMS key configuration
  - [ ] OIDC federation with AWS IAM
  - [ ] Environment variable setup
  - [ ] Troubleshooting guide

- [ ] **HashiCorp Vault Setup Guide**
  - [ ] Vault installation and configuration
  - [ ] JWT authentication method setup
  - [ ] Transit engine setup
  - [ ] OIDC-based policies
  - [ ] Policy configuration

- [ ] **Azure Key Vault Setup Guide**
  - [ ] Key Vault creation
  - [ ] Azure AD OIDC integration
  - [ ] Service Principal setup
  - [ ] Access policy configuration
  - [ ] Managed Identity setup

### Operational Guides
- [ ] **Provider Selection Guide**
  - [ ] Feature comparison matrix (including OIDC capabilities)
  - [ ] Performance characteristics
  - [ ] Cost considerations
  - [ ] Security features
  - [ ] Identity integration capabilities

- [ ] **OIDC Implementation Guide**
  - [ ] Identity-based vs vault-based key management
  - [ ] Token lifecycle management
  - [ ] Claim-based access control
  - [ ] Multi-tenant identity isolation
  - [ ] Performance optimization strategies

- [ ] **Migration Procedures**
  - [ ] Step-by-step migration guides
  - [ ] OIDC integration migration
  - [ ] Identity claim migration
  - [ ] Rollback procedures
  - [ ] Data validation steps
  - [ ] Downtime minimization strategies

---

## 🚨 Risk Mitigation

### Identified Risks
- [ ] **Data Loss Risk**
  - [ ] Backup procedures before testing
  - [ ] Key backup and recovery testing
  - [ ] Database snapshot procedures

- [ ] **Security Risk**
  - [ ] Test environment isolation
  - [ ] Credential management
  - [ ] Access logging and monitoring

- [ ] **Performance Risk**
  - [ ] Load testing in isolated environment
  - [ ] Gradual rollout procedures
  - [ ] Performance regression testing

### Mitigation Strategies
- [ ] Comprehensive backup procedures
- [ ] Isolated test environments
- [ ] Gradual deployment strategies
- [ ] Monitoring and alerting setup

---

## ✅ Success Criteria

### Functional Requirements
- [ ] All providers successfully encrypt/decrypt data
- [ ] Key rotation works across all providers
- [ ] Error handling is robust and informative
- [ ] Performance meets acceptable thresholds

### Non-Functional Requirements
- [ ] Security best practices implemented
- [ ] Comprehensive documentation available
- [ ] Automated testing suite created
- [ ] Monitoring and alerting configured

### Deliverables
- [ ] Test suite for all three providers
- [ ] Performance benchmark reports
- [ ] Security validation reports
- [ ] Configuration and operational documentation
- [ ] Migration procedures and scripts

---

## 📞 Support and Resources

### Team Responsibilities
- **DevOps Team**: Cloud provider account setup and access
- **Security Team**: Security review and validation
- **Development Team**: Test implementation and integration
- **QA Team**: Test execution and validation

### External Resources
- [ ] AWS KMS documentation and support
- [ ] HashiCorp Vault documentation and community
- [ ] Azure Key Vault documentation and support
- [ ] Cloud provider technical support contacts

---

---

## 🏗️ OIDC Implementation Architecture

### Key Derivation Strategies

#### Strategy 1: Deterministic Identity-Based Keys
```python
# Derive keys directly from JWT claims
def derive_key_from_identity(jwt_token: str, tenant_id: str) -> bytes:
    claims = validate_jwt(jwt_token)
    key_material = f"{claims['sub']}:{tenant_id}:{claims['iss']}"
    return pbkdf2_hmac('sha256', key_material.encode(), salt, iterations)
```

#### Strategy 2: Hybrid Identity + Vault
```python
# Use identity to select vault key
def get_vault_key_for_identity(jwt_token: str, tenant_id: str) -> str:
    claims = validate_jwt(jwt_token)
    key_id = f"tenant_{tenant_id}_user_{claims['sub']}"
    return vault_client.get_key(key_id)
```

#### Strategy 3: Dynamic Key Generation
```python
# Generate keys on-demand based on identity
def generate_dynamic_key(jwt_token: str, tenant_id: str) -> bytes:
    claims = validate_jwt(jwt_token)
    if not has_key_access(claims, tenant_id):
        raise UnauthorizedError()
    return generate_tenant_key(tenant_id, claims['sub'])
```

### Implementation Components

#### OIDC Key Vault Provider
- [ ] **Create `api/integrations/oidc_provider.py`**
  - [ ] JWT token validation
  - [ ] Claim extraction and mapping
  - [ ] Key derivation algorithms
  - [ ] Token refresh handling

#### OIDC Authentication Middleware
- [ ] **Create `api/middleware/oidc_auth_middleware.py`**
  - [ ] Request token extraction
  - [ ] Token validation pipeline
  - [ ] Identity context setup
  - [ ] Error handling

#### Identity-Based Encryption Service
- [ ] **Extend `api/services/encryption_service.py`**
  - [ ] Identity-aware key derivation
  - [ ] Claim-based access control
  - [ ] Multi-identity support
  - [ ] Token lifecycle management

### Security Considerations

#### Token Security
- [ ] **JWT Validation**
  - [ ] Signature verification (RS256/ES256)
  - [ ] Issuer validation
  - [ ] Audience validation
  - [ ] Expiration checking
  - [ ] Not-before validation

- [ ] **Claim Validation**
  - [ ] Required claim presence
  - [ ] Claim value validation
  - [ ] Custom claim processing
  - [ ] Tenant isolation enforcement

#### Key Security
- [ ] **Identity-Based Keys**
  - [ ] Deterministic but unpredictable derivation
  - [ ] Salt and iteration configuration
  - [ ] Key rotation strategies
  - [ ] Identity revocation handling

- [ ] **Access Control**
  - [ ] Claim-based authorization
  - [ ] Tenant boundary enforcement
  - [ ] Role-based key access
  - [ ] Time-based access control

### Performance Optimization

#### Caching Strategies
- [ ] **Token Caching**
  - [ ] Validated token cache
  - [ ] Claim extraction cache
  - [ ] Token blacklist cache
  - [ ] Refresh token handling

- [ ] **Key Caching**
  - [ ] Derived key cache
  - [ ] Identity-key mapping cache
  - [ ] Cache invalidation strategies
  - [ ] Memory management

#### Async Operations
- [ ] **Background Processing**
  - [ ] Async token validation
  - [ ] Background key derivation
  - [ ] Batch key operations
  - [ ] Queue-based processing

---

## 📋 OIDC Provider Integration Matrix

| Provider | JWT Support | Custom Claims | Federation | Refresh Tokens | MFA Claims |
|----------|-------------|---------------|------------|----------------|------------|
| Auth0 | ✅ RS256/HS256 | ✅ Rules/Actions | ✅ Social/Enterprise | ✅ Secure | ✅ MFA Claims |
| Azure AD | ✅ RS256 | ✅ Optional Claims | ✅ B2B/B2C | ✅ Secure | ✅ AMR Claims |
| Google | ✅ RS256 | ✅ Custom Attributes | ✅ Workspace | ✅ Secure | ✅ 2FA Claims |
| Keycloak | ✅ RS256/HS256 | ✅ Mappers | ✅ Identity Brokering | ✅ Configurable | ✅ Auth Methods |
| Okta | ✅ RS256 | ✅ Custom Claims | ✅ Universal Directory | ✅ Secure | ✅ Factor Claims |

---

**Next Steps**: 
1. **Phase 1**: Implement basic OIDC key derivation with one provider (Auth0 or Keycloak)
2. **Phase 2**: Add traditional key vault provider testing
3. **Phase 3**: Implement hybrid OIDC + vault integration
4. **Phase 4**: Multi-provider federation and advanced features

**Estimated Timeline**: 4 weeks for comprehensive testing across all providers including OIDC
**Resource Requirements**: 1-2 developers, access to cloud provider accounts, OIDC provider setup, test environment configuration

### OIDC Benefits for Encryption
- **Zero Trust**: No long-lived credentials stored
- **Identity-Centric**: Keys tied to user/service identity
- **Scalable**: Leverages existing identity infrastructure
- **Auditable**: Full identity and access audit trail
- **Flexible**: Works with any OIDC-compliant provider
- **Secure**: Modern cryptographic standards and practices