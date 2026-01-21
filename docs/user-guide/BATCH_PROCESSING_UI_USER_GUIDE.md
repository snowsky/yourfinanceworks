# Batch File Processing - UI User Guide

## Overview

This guide explains how to configure export destinations for batch file processing through the web interface. Export destinations determine where your processed batch results (CSV files) will be stored after OCR processing completes.

## Table of Contents

1. [Accessing Export Destinations](#accessing-export-destinations)
2. [Supported Destination Types](#supported-destination-types)
3. [Creating Export Destinations](#creating-export-destinations)
4. [Testing Connections](#testing-connections)
5. [Managing Destinations](#managing-destinations)
6. [Environment Variable Fallback](#environment-variable-fallback)
7. [Troubleshooting](#troubleshooting)

---

## Accessing Export Destinations

### Step 1: Navigate to Settings

1. Log into your account
2. Click on your profile icon in the top-right corner
3. Select **Settings** from the dropdown menu
4. Click on the **Export Destinations** tab

![Settings Navigation](images/settings-navigation.png)

### Step 2: View Export Destinations Tab

The Export Destinations tab displays:
- List of configured destinations
- Connection status indicators
- Quick actions (Edit, Test, Delete)
- "Add Destination" button

![Export Destinations Tab](images/export-destinations-tab.png)

---

## Supported Destination Types

The system supports four cloud storage providers:

### AWS S3
- **Use Case:** Amazon Web Services S3 buckets
- **Best For:** AWS-based infrastructure, high scalability
- **Credentials Required:** Access Key ID, Secret Access Key, Region, Bucket Name

### Azure Blob Storage
- **Use Case:** Microsoft Azure blob containers
- **Best For:** Azure-based infrastructure, enterprise environments
- **Credentials Required:** Connection String OR (Account Name + Account Key), Container Name

### Google Cloud Storage
- **Use Case:** Google Cloud Platform storage buckets
- **Best For:** GCP-based infrastructure, Google ecosystem
- **Credentials Required:** Service Account JSON OR (Project ID + Credentials), Bucket Name

### Google Drive
- **Use Case:** Google Drive folders
- **Best For:** Small teams, easy sharing, no cloud infrastructure needed
- **Credentials Required:** OAuth2 authorization, Folder ID

---

## Creating Export Destinations

### AWS S3 Destination

#### Step 1: Click "Add Destination"

Click the **Add Destination** button in the Export Destinations tab.

#### Step 2: Select Destination Type

From the dropdown menu, select **AWS S3**.

![Select AWS S3](images/select-aws-s3.png)

#### Step 3: Enter Destination Details

Fill in the following fields:

| Field | Description | Example | Required |
|-------|-------------|---------|----------|
| **Name** | Friendly name for this destination | "Production S3 Bucket" | Yes |
| **Access Key ID** | AWS access key ID | AKIAIOSFODNN7EXAMPLE | Yes |
| **Secret Access Key** | AWS secret access key | wJalrXUtnFEMI/K7MDENG... | Yes |
| **Region** | AWS region | us-east-1 | Yes |
| **Bucket Name** | S3 bucket name | my-exports | Yes |
| **Path Prefix** | Optional folder path within bucket | batch-results/ | No |
| **Set as Default** | Make this the default destination | ☑ | No |

![AWS S3 Form](images/aws-s3-form.png)

#### Step 4: Test Connection (Recommended)

Before saving, click **Test Connection** to verify your credentials work correctly.

- ✅ **Success:** Green checkmark with "Connection successful" message
- ❌ **Failure:** Red X with error details

#### Step 5: Save Destination

Click **Save** to create the destination. Your credentials will be encrypted before storage.

---

### Azure Blob Storage Destination

#### Step 1: Select Azure Blob Storage

From the destination type dropdown, select **Azure Blob Storage**.

#### Step 2: Choose Authentication Method

Azure supports two authentication methods:

**Option A: Connection String** (Recommended)
- Single string containing all authentication info
- Easier to configure
- Found in Azure Portal under Storage Account → Access Keys

**Option B: Account Name + Account Key**
- Separate fields for account name and key
- More granular control
- Also found in Azure Portal

![Azure Auth Methods](images/azure-auth-methods.png)

#### Step 3: Enter Credentials

**Using Connection String:**

| Field | Description | Required |
|-------|-------------|----------|
| **Name** | Friendly name | Yes |
| **Connection String** | Full Azure connection string | Yes |
| **Container Name** | Blob container name | Yes |
| **Path Prefix** | Optional folder path | No |

**Using Account Name + Key:**

| Field | Description | Required |
|-------|-------------|----------|
| **Name** | Friendly name | Yes |
| **Account Name** | Storage account name | Yes |
| **Account Key** | Storage account key | Yes |
| **Container Name** | Blob container name | Yes |
| **Path Prefix** | Optional folder path | No |

#### Step 4: Test and Save

1. Click **Test Connection** to verify
2. Click **Save** to create the destination

---

### Google Cloud Storage Destination

#### Step 1: Select Google Cloud Storage

From the destination type dropdown, select **Google Cloud Storage**.

#### Step 2: Choose Authentication Method

**Option A: Service Account JSON** (Recommended)
- Upload service account JSON file
- Most secure method
- Download from GCP Console → IAM & Admin → Service Accounts

**Option B: Project ID + Credentials**
- Manual entry of credentials
- More complex setup

![GCS Auth Methods](images/gcs-auth-methods.png)

#### Step 3: Enter Credentials

**Using Service Account JSON:**

| Field | Description | Required |
|-------|-------------|----------|
| **Name** | Friendly name | Yes |
| **Service Account JSON** | Upload .json file or paste content | Yes |
| **Bucket Name** | GCS bucket name | Yes |
| **Path Prefix** | Optional folder path | No |

#### Step 4: Test and Save

1. Click **Test Connection** to verify
2. Click **Save** to create the destination

---

### Google Drive Destination

#### Step 1: Select Google Drive

From the destination type dropdown, select **Google Drive**.

![Select Google Drive](images/select-google-drive.png)

#### Step 2: Authorize with Google

1. Click **Authorize with Google** button
2. Sign in to your Google account (if not already signed in)
3. Grant permissions to the application
4. You'll be redirected back to the settings page

![Google OAuth](images/google-oauth.png)

#### Step 3: Enter Folder ID

After authorization, enter the Google Drive folder ID where exports should be saved.

**Finding Your Folder ID:**
1. Open Google Drive in your browser
2. Navigate to the desired folder
3. Look at the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
4. Copy the folder ID from the URL

| Field | Description | Required |
|-------|-------------|----------|
| **Name** | Friendly name | Yes |
| **Folder ID** | Google Drive folder ID | Yes |

#### Step 4: Test and Save

1. Click **Test Connection** to verify folder access
2. Click **Save** to create the destination

---

## Testing Connections

### Why Test Connections?

Testing connections before saving ensures:
- Credentials are valid
- Bucket/container/folder exists
- Proper permissions are configured
- Network connectivity is working

### How to Test

#### Before Saving (Recommended)

1. Fill in all required fields
2. Click **Test Connection** button
3. Wait for test result (usually 2-5 seconds)
4. Review the result:
   - ✅ **Success:** Proceed to save
   - ❌ **Failure:** Review error message and fix issues

![Test Connection](images/test-connection.png)

#### After Saving

You can test existing destinations at any time:

1. Find the destination in the list
2. Click the **Test** button (🔍 icon)
3. Review the test result

### Test Result Indicators

| Indicator | Meaning | Action |
|-----------|---------|--------|
| ✅ Green checkmark | Last test successful | No action needed |
| ❌ Red X | Last test failed | Click to see error details |
| ⚠️ Yellow warning | Never tested | Test the connection |
| 🔄 Gray circle | Test in progress | Wait for result |

### Common Test Errors

#### AWS S3 Errors

**Error:** "Access Denied"
- **Cause:** Invalid credentials or insufficient permissions
- **Fix:** Verify Access Key ID and Secret Access Key, ensure IAM user has S3 permissions

**Error:** "Bucket does not exist"
- **Cause:** Bucket name is incorrect or doesn't exist
- **Fix:** Verify bucket name, ensure bucket exists in the specified region

**Error:** "Invalid region"
- **Cause:** Region doesn't match bucket location
- **Fix:** Check bucket region in AWS Console, update region field

#### Azure Errors

**Error:** "Authentication failed"
- **Cause:** Invalid connection string or account credentials
- **Fix:** Copy connection string again from Azure Portal

**Error:** "Container not found"
- **Cause:** Container name is incorrect or doesn't exist
- **Fix:** Verify container name in Azure Portal

#### Google Cloud Storage Errors

**Error:** "Invalid service account"
- **Cause:** Service account JSON is malformed or invalid
- **Fix:** Download fresh service account JSON from GCP Console

**Error:** "Insufficient permissions"
- **Cause:** Service account lacks storage permissions
- **Fix:** Grant "Storage Object Admin" role to service account

#### Google Drive Errors

**Error:** "Folder not found"
- **Cause:** Folder ID is incorrect or folder was deleted
- **Fix:** Verify folder ID from Google Drive URL

**Error:** "Access denied"
- **Cause:** OAuth token expired or permissions revoked
- **Fix:** Re-authorize with Google

---

## Managing Destinations

### Viewing Destinations

The destinations list shows:

| Column | Description |
|--------|-------------|
| **Name** | Destination name |
| **Type** | Cloud provider (S3, Azure, GCS, Drive) |
| **Status** | Active/Inactive |
| **Last Test** | Last test timestamp and result |
| **Default** | ⭐ if set as default |
| **Actions** | Edit, Test, Delete buttons |

![Destinations List](images/destinations-list.png)

### Editing Destinations

1. Click the **Edit** button (✏️ icon) next to the destination
2. Modify any fields (name, credentials, configuration)
3. Click **Test Connection** to verify changes
4. Click **Save** to update

**Note:** When updating credentials, you can update individual fields without re-entering all credentials.

### Setting Default Destination

The default destination is automatically selected when creating batch jobs via API.

**To set a destination as default:**
1. Edit the destination
2. Check the **Set as Default** checkbox
3. Save changes

**Note:** Only one destination can be default at a time. Setting a new default will unset the previous one.

### Deleting Destinations

**To delete a destination:**
1. Click the **Delete** button (🗑️ icon)
2. Confirm the deletion in the dialog
3. The destination will be soft-deleted (marked as inactive)

**Important:**
- You cannot delete a destination that's being used by active batch jobs
- Deleted destinations can be reactivated by editing and setting `is_active=true`
- Requires admin permissions

---

## Environment Variable Fallback

### What is Environment Variable Fallback?

If no export destination is configured in the UI, the system can use environment variables as fallback credentials. This is useful for:
- Development and testing
- Automated deployments
- Temporary configurations

### When Fallback is Used

The system uses environment variables when:
1. No export destinations are configured for your tenant
2. The specified destination ID doesn't exist
3. The destination has no credentials configured

### Fallback Notice

When no destinations are configured, you'll see a notice in the UI:

![Fallback Notice](images/fallback-notice.png)

> ℹ️ **No export destinations configured**
> 
> The system will use environment variables as fallback credentials. Configure a destination for better security and control.
> 
> [Learn more about environment variables](#environment-variables-reference)

### Environment Variables Reference

#### AWS S3

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=my-exports
AWS_S3_PATH_PREFIX=batch-results/  # optional
```

#### Azure Blob Storage

```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER=my-container
AZURE_STORAGE_PATH_PREFIX=batch-results/  # optional
```

#### Google Cloud Storage

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GCS_BUCKET_NAME=my-exports
GCS_PATH_PREFIX=batch-results/  # optional
```

**Note:** Google Drive does not support environment variable fallback.

### Best Practices

✅ **Do:**
- Use environment variables for development/testing
- Configure UI destinations for production
- Document which environment variables are required
- Use secrets management for production credentials

❌ **Don't:**
- Commit environment variables to version control
- Use environment variables in production (use UI configuration instead)
- Share environment variable values in plain text
- Mix environment variables and UI configuration

---

## Troubleshooting

### Issue: "Cannot save destination"

**Symptoms:**
- Save button doesn't work
- Error message appears
- Form validation fails

**Solutions:**
1. Ensure all required fields are filled
2. Check that credentials are in correct format
3. Verify you have proper permissions (non-viewer role)
4. Try testing connection first
5. Check browser console for JavaScript errors

### Issue: "Connection test fails"

**Symptoms:**
- Test returns error message
- Red X indicator appears
- Cannot save destination

**Solutions:**
1. Verify credentials are correct
2. Check bucket/container/folder exists
3. Ensure proper permissions are configured
4. Verify network connectivity
5. Check firewall rules
6. Review error message for specific details

### Issue: "Destination not appearing in list"

**Symptoms:**
- Saved destination doesn't show up
- List is empty
- Only some destinations visible

**Solutions:**
1. Refresh the page
2. Check if filtering is applied (active_only)
3. Verify destination was saved successfully
4. Check browser console for errors
5. Ensure you're viewing the correct tenant

### Issue: "Cannot delete destination"

**Symptoms:**
- Delete button is disabled
- Error message when attempting to delete
- Destination still appears after deletion

**Solutions:**
1. Verify you have admin permissions
2. Check if destination is being used by active batch jobs
3. Wait for active jobs to complete
4. Try soft delete (mark as inactive) instead

### Issue: "OAuth authorization fails (Google Drive)"

**Symptoms:**
- Redirect fails after Google login
- "Access denied" error
- Authorization button doesn't work

**Solutions:**
1. Ensure popup blockers are disabled
2. Check that redirect URL is configured correctly
3. Verify Google OAuth app is properly configured
4. Try clearing browser cookies
5. Use incognito/private browsing mode

### Issue: "Credentials are masked, can't see values"

**Symptoms:**
- Credentials show as `****XXXX`
- Cannot view full credentials
- Need to verify credentials

**Solutions:**
- This is expected behavior for security
- Credentials are always masked in the UI
- To update credentials, enter new values
- To verify credentials, use the Test Connection feature
- Original credentials are encrypted and cannot be retrieved

### Getting Help

If you continue to experience issues:

1. **Check the logs:**
   - Browser console (F12 → Console tab)
   - Server logs (if you have access)

2. **Review documentation:**
   - [API Reference](../api/docs/BATCH_FILE_PROCESSING_API_REFERENCE.md)
   - [Export Destinations API](../api/docs/EXPORT_DESTINATIONS_API.md)

3. **Contact support:**
   - Include error messages
   - Provide screenshots
   - Describe steps to reproduce
   - Mention browser and version

---

## Security Best Practices

### Credential Management

✅ **Do:**
- Use UI configuration for production credentials
- Test connections before saving
- Rotate credentials regularly
- Use least-privilege IAM policies
- Enable MFA on cloud accounts
- Monitor access logs

❌ **Don't:**
- Share credentials via email or chat
- Use root/admin credentials
- Store credentials in plain text
- Reuse credentials across environments
- Grant excessive permissions

### Access Control

- Only grant export destination configuration access to trusted users
- Use role-based access control (RBAC)
- Require admin approval for new destinations
- Audit destination configuration changes
- Review permissions regularly

### Monitoring

- Monitor connection test results
- Track export success/failure rates
- Set up alerts for repeated failures
- Review audit logs regularly
- Monitor cloud storage costs

---

## Appendix

### Credential Format Examples

#### AWS S3 Access Key ID Format
```
AKIAIOSFODNN7EXAMPLE
```
- Starts with `AKIA`
- 20 characters long
- Alphanumeric

#### Azure Connection String Format
```
DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=mykey;EndpointSuffix=core.windows.net
```

#### Google Service Account JSON Format
```json
{
  "type": "service_account",
  "project_id": "my-project",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "my-service-account@my-project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

### Supported Regions

#### AWS S3 Regions
- `us-east-1` - US East (N. Virginia)
- `us-east-2` - US East (Ohio)
- `us-west-1` - US West (N. California)
- `us-west-2` - US West (Oregon)
- `eu-west-1` - Europe (Ireland)
- `eu-central-1` - Europe (Frankfurt)
- `ap-southeast-1` - Asia Pacific (Singapore)
- `ap-northeast-1` - Asia Pacific (Tokyo)
- [Full list of AWS regions](https://docs.aws.amazon.com/general/latest/gr/rande.html)

### File Naming Conventions

Export files are named using the following pattern:

```
batch_export_{job_id}_{timestamp}.csv
```

Example:
```
batch_export_550e8400-e29b-41d4-a716-446655440000_20251108_103045.csv
```

### Retention Policies

Configure retention policies in the destination configuration:

```json
{
  "retention_days": 30
}
```

This will automatically delete export files older than 30 days (if supported by the destination).

---

## Quick Reference

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + S` | Save destination |
| `Ctrl/Cmd + T` | Test connection |
| `Esc` | Close dialog |

### Status Icons

| Icon | Meaning |
|------|---------|
| ✅ | Test successful |
| ❌ | Test failed |
| ⚠️ | Never tested |
| 🔄 | Test in progress |
| ⭐ | Default destination |
| 🔒 | Credentials encrypted |

### Common Tasks

| Task | Steps |
|------|-------|
| Add S3 destination | Settings → Export Destinations → Add → Select S3 → Fill form → Test → Save |
| Test connection | Find destination → Click Test button → Review result |
| Set as default | Edit destination → Check "Set as Default" → Save |
| Delete destination | Find destination → Click Delete → Confirm |

---

**Last Updated:** November 8, 2025  
**Version:** 1.0
