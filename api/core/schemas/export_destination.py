"""
Pydantic schemas for export destination management.

Defines credential schemas for different cloud storage providers
and export destination configuration.
"""

from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime


# ============================================================================
# S3 Credentials Schema
# ============================================================================

class S3Credentials(BaseModel):
    """AWS S3 credentials schema"""
    access_key_id: Optional[str] = Field(None, description="AWS Access Key ID (uses env var if not provided)")
    secret_access_key: Optional[str] = Field(None, description="AWS Secret Access Key (uses env var if not provided)")
    region: Optional[str] = Field(None, description="AWS Region (uses env var if not provided)")
    bucket_name: Optional[str] = Field(None, description="S3 Bucket name (uses env var if not provided)")
    path_prefix: Optional[str] = Field(None, description="Optional path prefix within bucket")

    @validator('region')
    def validate_region(cls, v):
        """Validate AWS region format"""
        if not v or len(v) < 3:
            raise ValueError("Invalid AWS region")
        return v

    @validator('bucket_name')
    def validate_bucket_name(cls, v):
        """Validate S3 bucket name"""
        if not v or len(v) < 3 or len(v) > 63:
            raise ValueError("Bucket name must be between 3 and 63 characters")
        return v


# ============================================================================
# Azure Credentials Schema
# ============================================================================

class AzureCredentialsConnectionString(BaseModel):
    """Azure Blob Storage credentials using connection string"""
    connection_string: str = Field(..., description="Azure Storage connection string")
    container_name: str = Field(..., description="Azure Blob container name")
    path_prefix: Optional[str] = Field(None, description="Optional path prefix within container")

    @validator('connection_string')
    def validate_connection_string(cls, v):
        """Validate Azure connection string format"""
        if not v or 'AccountName=' not in v or 'AccountKey=' not in v:
            raise ValueError("Invalid Azure connection string format")
        return v


class AzureCredentialsAccountKey(BaseModel):
    """Azure Blob Storage credentials using account name and key"""
    account_name: str = Field(..., description="Azure Storage account name")
    account_key: str = Field(..., description="Azure Storage account key")
    container_name: str = Field(..., description="Azure Blob container name")
    path_prefix: Optional[str] = Field(None, description="Optional path prefix within container")

    @validator('account_name')
    def validate_account_name(cls, v):
        """Validate Azure account name"""
        if not v or len(v) < 3 or len(v) > 24:
            raise ValueError("Account name must be between 3 and 24 characters")
        return v


# Union type for Azure credentials
AzureCredentials = Union[AzureCredentialsConnectionString, AzureCredentialsAccountKey]


# ============================================================================
# GCS Credentials Schema
# ============================================================================

class GCSCredentialsServiceAccount(BaseModel):
    """Google Cloud Storage credentials using service account JSON"""
    service_account_json: str = Field(..., description="Service account JSON key file content")
    bucket_name: str = Field(..., description="GCS bucket name")
    path_prefix: Optional[str] = Field(None, description="Optional path prefix within bucket")

    @validator('service_account_json')
    def validate_service_account_json(cls, v):
        """Validate service account JSON format"""
        import json
        try:
            data = json.loads(v)
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for service account")
        return v


class GCSCredentialsProjectId(BaseModel):
    """Google Cloud Storage credentials using project ID and credentials"""
    project_id: str = Field(..., description="GCP project ID")
    credentials: str = Field(..., description="GCP credentials JSON")
    bucket_name: str = Field(..., description="GCS bucket name")
    path_prefix: Optional[str] = Field(None, description="Optional path prefix within bucket")

    @validator('credentials')
    def validate_credentials(cls, v):
        """Validate credentials JSON format"""
        import json
        try:
            json.loads(v)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for credentials")
        return v


# Union type for GCS credentials
GCSCredentials = Union[GCSCredentialsServiceAccount, GCSCredentialsProjectId]


# ============================================================================
# Google Drive Credentials Schema
# ============================================================================

class GoogleDriveCredentials(BaseModel):
    """Google Drive credentials using OAuth2"""
    oauth_token: str = Field(..., description="OAuth2 access token")
    refresh_token: str = Field(..., description="OAuth2 refresh token")
    folder_id: str = Field(..., description="Google Drive folder ID")

    @validator('folder_id')
    def validate_folder_id(cls, v):
        """Validate Google Drive folder ID format"""
        if not v or len(v) < 10:
            raise ValueError("Invalid Google Drive folder ID")
        return v


# ============================================================================
# Export Destination Configuration Schemas
# ============================================================================

class ExportDestinationCreate(BaseModel):
    """Schema for creating a new export destination"""
    name: str = Field(..., description="User-friendly name for the destination")
    destination_type: str = Field(..., description="Type of destination: s3, azure, gcs, google_drive")
    credentials: Dict[str, Any] = Field(..., description="Destination-specific credentials")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")
    is_default: bool = Field(False, description="Set as default destination")

    @validator('destination_type')
    def validate_destination_type(cls, v):
        """Validate destination type"""
        allowed_types = ['s3', 'azure', 'gcs', 'google_drive']
        if v not in allowed_types:
            raise ValueError(f"Destination type must be one of: {', '.join(allowed_types)}")
        return v

    @validator('name')
    def validate_name(cls, v):
        """Validate destination name"""
        if not v or len(v) < 3 or len(v) > 200:
            raise ValueError("Name must be between 3 and 200 characters")
        return v


class ExportDestinationUpdate(BaseModel):
    """Schema for updating an export destination"""
    name: Optional[str] = Field(None, description="User-friendly name for the destination")
    credentials: Optional[Dict[str, Any]] = Field(None, description="Updated credentials")
    config: Optional[Dict[str, Any]] = Field(None, description="Updated configuration")
    is_active: Optional[bool] = Field(None, description="Active status")
    is_default: Optional[bool] = Field(None, description="Default status")

    @validator('name')
    def validate_name(cls, v):
        """Validate destination name"""
        if v is not None and (len(v) < 3 or len(v) > 200):
            raise ValueError("Name must be between 3 and 200 characters")
        return v


class ExportDestinationResponse(BaseModel):
    """Schema for export destination response"""
    id: int
    tenant_id: int
    name: str
    destination_type: str
    is_active: bool
    is_default: bool
    config: Optional[Dict[str, Any]]
    masked_credentials: Optional[Dict[str, str]]  # Masked version of credentials
    last_test_at: Optional[datetime]
    last_test_success: Optional[bool]
    last_test_error: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[int]

    class Config:
        from_attributes = True


class ExportDestinationTestResult(BaseModel):
    """Schema for connection test result"""
    success: bool
    message: str
    error_details: Optional[str] = None
    tested_at: datetime


class ExportDestinationList(BaseModel):
    """Schema for list of export destinations"""
    destinations: list[ExportDestinationResponse]
    total: int
