# Cloud Storage Configuration Scripts Reference

This document provides detailed reference documentation for the cloud storage configuration management scripts.

## Overview

The cloud storage system includes four main configuration management scripts:

1. **`validate_cloud_storage_config.py`** - Configuration validation and connectivity testing
2. **`setup_cloud_storage.py`** - Interactive setup wizard for cloud providers
3. **`cloud_storage_deployment_check.py`** - Pre-deployment readiness checks
4. **`manage_cloud_storage_config.py`** - Environment configuration management

## Script Details

### 1. validate_cloud_storage_config.py

**Purpose**: Validates cloud storage configuration and tests connectivity to configured providers.

#### Usage

```bash
python api/scripts/validate_cloud_storage_config.py [OPTIONS]
```

#### Options

- `--provider {aws_s3,azure_blob,gcp_storage,local}` - Test specific provider only
- `--fix-permissions` - Attempt to fix permission issues (placeholder)
- `--verbose, -v` - Enable verbose output
- `--json` - Output results in JSON format

#### Examples

```bash
# Validate all configuration
python api/scripts/validate_cloud_storage_config.py

# Test specific provider with verbose output
python api/scripts/validate_cloud_storage_config.py --provider aws_s3 --verbose

# Get JSON output for automation
python api/scripts/validate_cloud_storage_config.py --json
```

#### Output

The script provides detailed validation results including:
- Configuration syntax validation
- Provider connectivity tests
- Permission checks (placeholder)
- File operation tests (placeholder)
- Summary with recommendations

#### Exit Codes

- `0` - All validations passed
- `1` - Validation failures found

---

### 2. setup_cloud_storage.py

**Purpose**: Interactive setup wizard that guides users through cloud storage provider configuration.

#### Usage

```bash
python api/scripts/setup_cloud_storage.py [OPTIONS]
```

#### Options

- `--provider {aws_s3,azure_blob,gcp_storage}` - Set up specific provider only
- `--interactive` - Run interactive setup (default: true)
- `--dry-run` - Show what would be done without making changes
- `--verbose, -v` - Enable verbose output

#### Examples

```bash
# Interactive setup for all providers
python api/scripts/setup_cloud_storage.py --interactive

# Set up only AWS S3 with dry run
python api/scripts/setup_cloud_storage.py --provider aws_s3 --dry-run

# Verbose setup
python api/scripts/setup_cloud_storage.py --verbose
```

#### Features

- **Provider Selection**: Choose which cloud providers to configure
- **Authentication Setup**: Configure credentials for each provider
- **Resource Creation**: Create buckets/containers if they don't exist
- **Configuration Testing**: Test connectivity during setup
- **File Generation**: Generate `.env` configuration files

#### Interactive Flow

1. **Provider Selection**: Choose from AWS S3, Azure Blob, GCP Storage
2. **Basic Configuration**: Set bucket names, regions, etc.
3. **Authentication**: Configure access keys, connection strings, or service accounts
4. **Advanced Options**: Storage classes, encryption, lifecycle policies
5. **Testing**: Validate configuration and test connectivity
6. **File Generation**: Create environment configuration files

---

### 3. cloud_storage_deployment_check.py

**Purpose**: Comprehensive pre-deployment readiness checks for cloud storage configuration.

#### Usage

```bash
python api/scripts/cloud_storage_deployment_check.py [OPTIONS]
```

#### Options

- `--environment {development,staging,production}` - Target deployment environment (default: production)
- `--fix-issues` - Attempt to fix issues automatically
- `--verbose, -v` - Enable verbose output
- `--json` - Output results in JSON format

#### Examples

```bash
# Check production readiness
python api/scripts/cloud_storage_deployment_check.py --environment production

# Check with automatic fixes
python api/scripts/cloud_storage_deployment_check.py --fix-issues --verbose

# Staging environment check
python api/scripts/cloud_storage_deployment_check.py --environment staging
```

#### Checks Performed

1. **Environment Variables**: Verify all required variables are set
2. **Dependencies**: Check Python package installations
3. **Configuration**: Validate configuration syntax and logic
4. **Connectivity**: Test connections to all enabled providers
5. **Permissions**: Validate access permissions (placeholder)
6. **Security**: Check security settings and best practices
7. **Performance**: Validate performance-related settings

#### Output

Provides a comprehensive deployment readiness report with:
- Overall deployment status
- Detailed check results
- Critical issues that must be fixed
- Warnings and recommendations
- Applied fixes (if `--fix-issues` used)

#### Exit Codes

- `0` - Ready for deployment
- `1` - Issues found, not ready for deployment

---

### 4. manage_cloud_storage_config.py

**Purpose**: Manage cloud storage configuration across different environments with version control and comparison capabilities.

#### Usage

```bash
python api/scripts/manage_cloud_storage_config.py COMMAND [OPTIONS]
```

#### Commands

##### generate

Generate configuration for a specific environment.

```bash
python api/scripts/manage_cloud_storage_config.py generate ENVIRONMENT [OPTIONS]
```

**Options**:
- `ENVIRONMENT` - Environment name (development, staging, production)
- `--providers PROVIDERS` - Cloud providers to configure (default: aws_s3)
- `--interactive` - Interactive configuration mode

**Examples**:
```bash
# Generate production config with AWS S3 and Azure
python api/scripts/manage_cloud_storage_config.py generate production --providers aws_s3 azure_blob

# Interactive staging configuration
python api/scripts/manage_cloud_storage_config.py generate staging --interactive
```

##### validate

Validate configuration for a specific environment.

```bash
python api/scripts/manage_cloud_storage_config.py validate ENVIRONMENT
```

**Examples**:
```bash
# Validate production configuration
python api/scripts/manage_cloud_storage_config.py validate production
```

##### deploy

Deploy configuration to target environment.

```bash
python api/scripts/manage_cloud_storage_config.py deploy ENVIRONMENT [OPTIONS]
```

**Options**:
- `--target TARGET` - Target file (default: .env)

**Examples**:
```bash
# Deploy production config to .env
python api/scripts/manage_cloud_storage_config.py deploy production

# Deploy to custom file
python api/scripts/manage_cloud_storage_config.py deploy staging --target .env.staging
```

##### compare

Compare configurations between two environments.

```bash
python api/scripts/manage_cloud_storage_config.py compare ENV1 ENV2
```

**Examples**:
```bash
# Compare staging and production
python api/scripts/manage_cloud_storage_config.py compare staging production
```

##### backup

Backup current configuration.

```bash
python api/scripts/manage_cloud_storage_config.py backup [OPTIONS]
```

**Options**:
- `--source SOURCE` - Source file (default: .env)

**Examples**:
```bash
# Backup current .env file
python api/scripts/manage_cloud_storage_config.py backup
```

##### restore

Restore configuration from backup.

```bash
python api/scripts/manage_cloud_storage_config.py restore BACKUP_FILE [OPTIONS]
```

**Options**:
- `--target TARGET` - Target file (default: .env)

**Examples**:
```bash
# Restore from backup
python api/scripts/manage_cloud_storage_config.py restore config/backups/env_backup_20231201_120000.env
```

##### list

List available configurations or backups.

```bash
python api/scripts/manage_cloud_storage_config.py list {configs,backups}
```

**Examples**:
```bash
# List available environment configs
python api/scripts/manage_cloud_storage_config.py list configs

# List available backups
python api/scripts/manage_cloud_storage_config.py list backups
```

#### Global Options

- `--verbose, -v` - Enable verbose output

## Configuration Files

### Environment Templates

The scripts work with environment-specific configuration files stored in `api/config/environments/`:

- `development.env` - Development environment settings
- `staging.env` - Staging environment settings  
- `production.env` - Production environment settings

### Backup Files

Backup files are stored in `api/config/backups/` with timestamp naming:
- Format: `{original_name}_backup_{YYYYMMDD_HHMMSS}.env`
- Example: `env_backup_20231201_120000.env`

## Environment-Specific Defaults

### Development Environment

```bash
CLOUD_STORAGE_ENABLED=false
CLOUD_STORAGE_PRIMARY_PROVIDER=local
CLOUD_STORAGE_FALLBACK_ENABLED=true
STORAGE_OPERATION_LOGGING_ENABLED=true
STORAGE_PERFORMANCE_MONITORING_ENABLED=false
STORAGE_COST_OPTIMIZATION_ENABLED=false
STORAGE_AUDIT_LOGGING_ENABLED=false
STORAGE_TENANT_ISOLATION_ENABLED=false
```

### Staging Environment

```bash
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3
CLOUD_STORAGE_FALLBACK_ENABLED=true
STORAGE_OPERATION_LOGGING_ENABLED=true
STORAGE_PERFORMANCE_MONITORING_ENABLED=true
STORAGE_AUDIT_LOGGING_ENABLED=true
STORAGE_TENANT_ISOLATION_ENABLED=true
```

### Production Environment

```bash
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3
CLOUD_STORAGE_FALLBACK_ENABLED=true
STORAGE_OPERATION_LOGGING_ENABLED=true
STORAGE_PERFORMANCE_MONITORING_ENABLED=true
STORAGE_COST_OPTIMIZATION_ENABLED=true
STORAGE_AUDIT_LOGGING_ENABLED=true
STORAGE_TENANT_ISOLATION_ENABLED=true
STORAGE_CROSS_REGION_REPLICATION_ENABLED=true
STORAGE_VERSIONING_ENABLED=true
```

## Integration with Existing System

### Dependencies

All scripts integrate with the existing cloud storage system:

- **`storage_config.cloud_storage_config`** - Configuration classes
- **`CloudStorageConfig`** - Main configuration class
- **`CloudStorageConfigurationManager`** - Configuration management
- **`StorageProvider`** - Provider enumeration

### Error Handling

Scripts provide comprehensive error handling:
- Configuration validation errors
- Network connectivity issues
- Authentication failures
- Permission problems
- Missing dependencies

### Logging

All scripts support verbose logging:
- Configuration validation steps
- Provider connectivity tests
- File operations
- Error details and stack traces

## Automation and CI/CD Integration

### JSON Output

All validation scripts support JSON output for automation:

```bash
# Get JSON results for CI/CD
python api/scripts/validate_cloud_storage_config.py --json > validation_results.json
python api/scripts/cloud_storage_deployment_check.py --json > deployment_check.json
```

### Exit Codes

Scripts use standard exit codes for automation:
- `0` - Success
- `1` - Failure/Issues found

### Batch Operations

Example CI/CD pipeline integration:

```bash
#!/bin/bash
# Cloud storage deployment pipeline

# 1. Validate configuration
python api/scripts/validate_cloud_storage_config.py --json > validation.json
if [ $? -ne 0 ]; then
    echo "Configuration validation failed"
    exit 1
fi

# 2. Check deployment readiness
python api/scripts/cloud_storage_deployment_check.py --environment production --json > deployment.json
if [ $? -ne 0 ]; then
    echo "Deployment check failed"
    exit 1
fi

# 3. Deploy configuration
python api/scripts/manage_cloud_storage_config.py deploy production

echo "Cloud storage deployment completed successfully"
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   ModuleNotFoundError: No module named 'storage_config'
   ```
   - Ensure you're running scripts from the correct directory
   - Check Python path includes the API directory

2. **Configuration Validation Failures**
   ```bash
   ValueError: Cloud storage configuration validation failed
   ```
   - Check required environment variables are set
   - Verify provider-specific configuration requirements
   - Use `--verbose` flag for detailed error information

3. **Connectivity Test Failures**
   ```bash
   Connection test failed: Invalid credentials
   ```
   - Verify authentication credentials
   - Check network connectivity to cloud providers
   - Ensure proper IAM permissions

4. **Permission Issues**
   ```bash
   PermissionError: No write permission to: ./config/environments
   ```
   - Check file system permissions
   - Ensure directories exist and are writable

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Run with verbose flag
python api/scripts/validate_cloud_storage_config.py --verbose
```

### Log Analysis

Check application logs for detailed error information:

```bash
# Filter cloud storage related logs
grep -i "cloud.*storage\|s3\|azure\|gcs" /var/log/app.log

# Check configuration errors
grep -E "(ConfigurationError|ValidationError)" /var/log/app.log
```

## Best Practices

### Security

1. **Credential Management**
   - Use environment variables for sensitive data
   - Never commit credentials to version control
   - Use IAM roles in production when possible
   - Rotate credentials regularly

2. **Configuration Validation**
   - Always validate configuration before deployment
   - Test connectivity in staging environment first
   - Use deployment checks in CI/CD pipelines

3. **Backup and Recovery**
   - Backup configurations before changes
   - Test restore procedures regularly
   - Keep multiple backup versions

### Performance

1. **Batch Operations**
   - Use JSON output for automated processing
   - Run validation checks in parallel when possible
   - Cache validation results for repeated operations

2. **Resource Management**
   - Clean up temporary files and connections
   - Use appropriate timeout values
   - Monitor resource usage during operations

### Maintenance

1. **Regular Validation**
   - Schedule periodic configuration validation
   - Monitor provider connectivity
   - Check for configuration drift

2. **Documentation**
   - Keep configuration documentation updated
   - Document environment-specific settings
   - Maintain change logs for configuration updates

## Support and Resources

- **Main Documentation**: `docs/CLOUD_STORAGE_DEPLOYMENT_GUIDE.md`
- **Configuration Guide**: `api/config/README.md`
- **Source Code**: `api/scripts/` directory
- **Configuration Classes**: `api/storage_config/cloud_storage_config.py`

For additional support, refer to the troubleshooting sections in the main deployment guide or contact the development team.