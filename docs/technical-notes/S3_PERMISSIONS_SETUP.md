# AWS S3 Permissions Setup Guide

This guide explains how to configure AWS S3 permissions for the Invoice Application's cloud storage functionality.

## Overview

The Invoice Application uses AWS S3 to store file attachments (receipts, invoices, documents) with tenant isolation and security features. Proper IAM permissions are required for the application to upload, download, and manage files in your S3 bucket.

## Prerequisites

- AWS Account with S3 bucket created
- AWS IAM user or role for the application
- AWS CLI installed (optional, for command-line setup)

## Required S3 Permissions

The application requires the following S3 permissions:

### Bucket-Level Permissions
- `s3:ListBucket` - List objects in the bucket
- `s3:GetBucketLocation` - Get bucket region information
- `s3:GetBucketVersioning` - Check versioning status (if enabled)

### Object-Level Permissions
- `s3:GetObject` - Download files from S3
- `s3:PutObject` - Upload files to S3
- `s3:DeleteObject` - Delete files from S3
- `s3:GetObjectVersion` - Access versioned objects (if versioning enabled)
- `s3:DeleteObjectVersion` - Delete versioned objects (if versioning enabled)

## IAM Policy Configuration

### Method 1: Using AWS Console

1. **Navigate to IAM Console**
   - Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
   - Click on "Users" in the left sidebar

2. **Find Your Application User**
   - Locate the IAM user used by your application
   - Click on the username to open user details

3. **Create and Attach Policy**
   - Click on "Add permissions" → "Attach policies directly"
   - Click "Create policy"
   - Switch to the "JSON" tab
   - Copy and paste the policy JSON below

4. **IAM Policy JSON**
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Sid": "S3BucketAccess",
               "Effect": "Allow",
               "Action": [
                   "s3:ListBucket",
                   "s3:GetBucketLocation",
                   "s3:GetBucketVersioning"
               ],
               "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME"
           },
           {
               "Sid": "S3ObjectAccess",
               "Effect": "Allow",
               "Action": [
                   "s3:GetObject",
                   "s3:PutObject",
                   "s3:DeleteObject",
                   "s3:GetObjectVersion",
                   "s3:DeleteObjectVersion"
               ],
               "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
           }
       ]
   }
   ```

5. **Replace Placeholder**
   - Replace `YOUR_BUCKET_NAME` with your actual S3 bucket name
   - Example: `arn:aws:s3:::my-invoice-app-bucket`

6. **Save and Attach**
   - Click "Next: Tags" → "Next: Review"
   - Name the policy (e.g., "InvoiceAppS3Access")
   - Click "Create policy"
   - Go back to your user and attach the newly created policy

### Method 2: Using AWS CLI

1. **Save Policy to File**
   ```bash
   # Create policy file
   cat > invoice-app-s3-policy.json << 'EOF'
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Sid": "S3BucketAccess",
               "Effect": "Allow",
               "Action": [
                   "s3:ListBucket",
                   "s3:GetBucketLocation",
                   "s3:GetBucketVersioning"
               ],
               "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME"
           },
           {
               "Sid": "S3ObjectAccess",
               "Effect": "Allow",
               "Action": [
                   "s3:GetObject",
                   "s3:PutObject",
                   "s3:DeleteObject",
                   "s3:GetObjectVersion",
                   "s3:DeleteObjectVersion"
               ],
               "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
           }
       ]
   }
   EOF
   ```

2. **Update Bucket Name**
   ```bash
   # Replace YOUR_BUCKET_NAME with your actual bucket name
   sed -i 's/YOUR_BUCKET_NAME/my-invoice-app-bucket/g' invoice-app-s3-policy.json
   ```

3. **Apply Policy**
   ```bash
   # Attach policy to user
   aws iam put-user-policy \
     --user-name YOUR_IAM_USERNAME \
     --policy-name InvoiceAppS3Access \
     --policy-document file://invoice-app-s3-policy.json
   ```

### Method 3: Using Terraform

```hcl
# Define the IAM policy
resource "aws_iam_policy" "invoice_app_s3_policy" {
  name        = "InvoiceAppS3Access"
  description = "S3 permissions for Invoice Application"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BucketAccess"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning"
        ]
        Resource = "arn:aws:s3:::${var.s3_bucket_name}"
      },
      {
        Sid    = "S3ObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetObjectVersion",
          "s3:DeleteObjectVersion"
        ]
        Resource = "arn:aws:s3:::${var.s3_bucket_name}/*"
      }
    ]
  })
}

# Attach policy to user
resource "aws_iam_user_policy_attachment" "invoice_app_s3_attachment" {
  user       = var.iam_username
  policy_arn = aws_iam_policy.invoice_app_s3_policy.arn
}
```

## Environment Configuration

After setting up IAM permissions, configure your application environment:

### 1. Update .env File

```bash
# Cloud Storage Configuration
CLOUD_STORAGE_ENABLED=true
CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3
CLOUD_STORAGE_FALLBACK_ENABLED=true
CLOUD_STORAGE_FALLBACK_PROVIDER=local

# AWS S3 Configuration
AWS_S3_ENABLED=true
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_S3_REGION=us-east-1
AWS_S3_ACCESS_KEY_ID=your-access-key-id
AWS_S3_SECRET_ACCESS_KEY=your-secret-access-key
AWS_S3_STORAGE_CLASS=STANDARD
AWS_S3_SERVER_SIDE_ENCRYPTION=AES256
```

### 2. Security Best Practices

- **Use IAM Roles**: In production, prefer IAM roles over access keys
- **Principle of Least Privilege**: Only grant necessary permissions
- **Rotate Keys**: Regularly rotate access keys
- **Enable MFA**: Enable multi-factor authentication for IAM users
- **Monitor Access**: Use CloudTrail to monitor S3 access

## File Organization Structure

The application organizes files in S3 using the following structure:

```
your-bucket-name/
├── tenant_1/
│   ├── expenses/
│   │   ├── 123_1640995200_receipt.pdf
│   │   └── 124_1640995300_invoice.jpg
│   ├── invoices/
│   │   └── 456_1640995400_document.pdf
│   └── inventory/
│       └── 789_1640995500_image.png
├── tenant_2/
│   ├── expenses/
│   └── invoices/
└── test/
    └── config_test.txt
```

## Testing S3 Configuration

### 1. Run Permission Check

```bash
# In your application container
docker exec -it invoice_app_api python check_s3_permissions.py
```

Expected output for properly configured permissions:
```
🧪 Testing S3 Operations:
✅ s3:HeadBucket - SUCCESS
✅ s3:ListBucket - SUCCESS
✅ s3:PutObject - SUCCESS
✅ s3:GetObject - SUCCESS
✅ s3:DeleteObject - SUCCESS
```

### 2. Test File Upload

```bash
# Test expense attachment upload
docker exec -it invoice_app_api python test_expense_upload.py
```

Expected output:
```
✅ Expense attachment uploaded successfully!
   File key: tenant_1/expenses/12345_1640995200_test_expense_receipt.pdf
   Provider: aws_s3
   File size: 62 bytes
```

### 3. Verify in AWS Console

1. Go to [S3 Console](https://console.aws.amazon.com/s3/)
2. Navigate to your bucket
3. Look for files under `tenant_X/expenses/` or `tenant_X/invoices/`

## Troubleshooting

### Common Issues

#### 1. AccessDenied Error
```
Error: User is not authorized to perform: s3:PutObject
```
**Solution**: Verify IAM policy includes `s3:PutObject` permission

#### 2. NoSuchBucket Error
```
Error: The specified bucket does not exist
```
**Solution**: Check bucket name in environment variables

#### 3. Files Not Appearing in S3
**Symptoms**: Expenses created but no files in S3 bucket
**Cause**: Application falling back to local storage due to permission issues
**Solution**: Run permission check script and fix IAM permissions

#### 4. Region Mismatch
```
Error: The bucket is in this region: us-west-2
```
**Solution**: Update `AWS_S3_REGION` in environment variables

### Debug Commands

```bash
# Check current IAM user
aws sts get-caller-identity

# List bucket contents
aws s3 ls s3://your-bucket-name/ --recursive

# Test bucket access
aws s3 cp test.txt s3://your-bucket-name/test.txt
aws s3 rm s3://your-bucket-name/test.txt
```

## Security Considerations

### 1. Bucket Policy (Optional)

For additional security, you can add a bucket policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "RestrictToApplicationUser",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:user/YOUR_IAM_USERNAME"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
        }
    ]
}
```

### 2. Server-Side Encryption

The application automatically enables AES256 server-side encryption. For KMS encryption:

```bash
# Environment variables
AWS_S3_SERVER_SIDE_ENCRYPTION=aws:kms
AWS_S3_KMS_KEY_ID=your-kms-key-id
```

### 3. CORS Configuration (if needed)

If accessing files from web browsers:

```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedOrigins": ["https://your-domain.com"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000
    }
]
```

## Monitoring and Logging

### 1. CloudTrail

Enable CloudTrail to monitor S3 API calls:

```json
{
    "eventVersion": "1.05",
    "userIdentity": {
        "type": "IAMUser",
        "principalId": "AIDACKCEVSQ6C2EXAMPLE",
        "arn": "arn:aws:iam::123456789012:user/invoice-app",
        "accountId": "123456789012",
        "userName": "invoice-app"
    },
    "eventTime": "2023-01-01T12:00:00Z",
    "eventSource": "s3.amazonaws.com",
    "eventName": "PutObject",
    "resources": [
        {
            "ARN": "arn:aws:s3:::your-bucket/tenant_1/expenses/receipt.pdf",
            "type": "AWS::S3::Object"
        }
    ]
}
```

### 2. Application Logs

The application logs all storage operations:

```
INFO: Successfully stored file tenant_1/expenses/123_receipt.pdf with primary provider aws_s3
INFO: File uploaded to S3: tenant_1/expenses/123_receipt.pdf (1024 bytes)
```

## Cost Optimization

### 1. Storage Classes

Configure appropriate storage classes:

```bash
# Standard for frequently accessed files
AWS_S3_STORAGE_CLASS=STANDARD

# Standard-IA for infrequently accessed files
AWS_S3_STORAGE_CLASS=STANDARD_IA

# Glacier for archival
AWS_S3_STORAGE_CLASS=GLACIER
```

### 2. Lifecycle Policies

Set up lifecycle policies to automatically transition or delete old files:

```json
{
    "Rules": [
        {
            "ID": "InvoiceAppLifecycle",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "tenant_"
            },
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 365,
                    "StorageClass": "GLACIER"
                }
            ]
        }
    ]
}
```

## Support

If you encounter issues:

1. Run the diagnostic scripts provided
2. Check AWS CloudTrail logs
3. Verify IAM permissions match this guide
4. Ensure environment variables are correctly set
5. Check application logs for detailed error messages

For additional help, refer to:
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [AWS IAM Documentation](https://docs.aws.amazon.com/iam/)
- Application logs in the container