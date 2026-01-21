# License Activation Guide

## Overview

This guide explains how to activate your license, understand the trial period, and manage your feature licenses in the {APP_NAME}.

## Table of Contents

1. [Trial Period](#trial-period)
2. [Activating Your License](#activating-your-license)
3. [Viewing License Status](#viewing-license-status)
4. [Purchasing Additional Features](#purchasing-additional-features)
5. [FAQ](#faq)

---

## Trial Period

### What is the Trial Period?

When you first install the {APP_NAME}, you automatically receive a **30-day free trial** with access to all features. This allows you to evaluate the system before purchasing a license.

### Trial Features

During the trial period, you have full access to:
- ✅ All AI-powered features (invoice processing, expense OCR, bank statements, chat assistant)
- ✅ All integrations (tax services, Slack, cloud storage, SSO)
- ✅ All advanced features (approvals, reporting, batch processing, inventory)

### Grace Period

After your 30-day trial expires, you enter a **7-day grace period**. During this time:
- ⚠️ You can still access all features
- ⚠️ You'll see warnings about license expiration
- ⚠️ You should activate a license to continue using premium features

### After Grace Period

Once the grace period ends (37 days after installation):
- ❌ Premium features will be disabled
- ✅ Core features (invoices, expenses, clients) remain available
- 📧 You'll need to purchase and activate a license to restore premium features

---

## Activating Your License

### Step 1: Obtain Your License Key

After purchasing a license, you'll receive an email containing:
- Your unique license key (a long string of characters)
- List of enabled features
- License expiration date
- Activation instructions

**Example License Key:**
```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImN1c3RvbWVyQGV4YW1wbGUuY29tIiwibmFtZSI6IkFjbWUgQ29ycCIsImZlYXR1cmVzIjpbImFpX2ludm9pY2UiLCJhaV9leHBlbnNlIiwidGF4X2ludGVncmF0aW9uIl0sImV4cCI6MTc0MDAwMDAwMH0.signature...
```

### Step 2: Navigate to License Management

1. Log in to your {APP_NAME}
2. Click on your profile icon in the top-right corner
3. Select **"Settings"** from the dropdown menu
4. Click on the **"License"** tab in the settings page

### Step 3: Enter Your License Key

1. In the License Management page, locate the **"Activate License"** section
2. Paste your license key into the text field
3. Click the **"Activate License"** button
4. Wait for the confirmation message

### Step 4: Verify Activation

After successful activation, you should see:
- ✅ Green checkmark indicating "License Active"
- 📅 License expiration date
- 📋 List of enabled features
- 🔄 License details (customer name, email)

### Troubleshooting Activation

If activation fails, check:
- ✓ License key is copied completely (no extra spaces)
- ✓ License has not expired
- ✓ You're connected to the internet
- ✓ License key is valid for your installation

---

## Viewing License Status

### License Management Dashboard

Access your license information at any time:

**Path:** Settings → License

**Information Displayed:**
- **Status:** Trial, Active, Expired, or Grace Period
- **Type:** Trial or Licensed
- **Expiration Date:** When your license expires
- **Days Remaining:** Countdown to expiration
- **Enabled Features:** List of features you can access

### Trial Banner

When in trial mode, you'll see a banner at the top of the application:

```
🎉 Trial Mode: 23 days remaining
You have full access to all features. Purchase a license to continue after trial.
[Purchase License]
```

### Expiration Warnings

You'll receive warnings when your license is approaching expiration:

- **30 days before:** Gentle reminder in the dashboard
- **7 days before:** Warning banner appears
- **On expiration:** Features are disabled, upgrade prompt shown

---

## Purchasing Additional Features

### Available Feature Modules

The {APP_NAME} offers the following licensable features:

#### AI-Powered Features
- **AI Invoice Processing** - Automatic invoice data extraction using AI
- **AI Expense Processing** - OCR and categorization for expense receipts
- **AI Bank Statement Processing** - Parse and extract bank statement data
- **AI Chat Assistant** - Conversational AI for accounting questions

#### Integration Features
- **Tax Service Integration** - Automated tax tracking and reporting
- **Slack Integration** - Slack bot for notifications and commands
- **Cloud Storage** - AWS S3, Azure Blob, and GCP Storage support
- **SSO Authentication** - Google and Azure AD single sign-on

#### Advanced Features
- **Approval Workflows** - Multi-level expense and invoice approvals
- **Reporting & Analytics** - Custom reports and dashboards
- **Batch Processing** - Bulk file uploads and processing
- **Inventory Management** - Product inventory tracking
- **Advanced Search** - Full-text search across all entities
- **CRM Module** - Customer relationship management

### How to Purchase

1. **Visit the Pricing Page**
   - Click the **"Purchase License"** button in the License Management page
   - Or visit: `https://yourdomain.com/pricing`

2. **Select Your Features**
   - Choose individual features or feature bundles
   - See pricing for each feature module
   - Select license duration (1 year, 2 years, etc.)

3. **Complete Checkout**
   - Enter your payment information (Stripe secure checkout)
   - Provide your email address for license delivery
   - Complete the purchase

4. **Receive Your License**
   - License key is emailed within 1 minute
   - Follow the activation steps above
   - Features are enabled immediately upon activation

### Upgrading Your License

To add features to an existing license:

1. Purchase the additional features
2. You'll receive a new license key with all features
3. Activate the new license key (replaces the old one)
4. All features are now available

---

## FAQ

### General Questions

**Q: What happens if I don't activate a license after the trial?**

A: After the 37-day trial + grace period, premium features will be disabled. Core features (invoices, expenses, clients) remain available. You can activate a license at any time to restore premium features.

**Q: Can I extend my trial period?**

A: The trial period is fixed at 30 days with a 7-day grace period. Contact sales if you need additional evaluation time.

**Q: Do I need an internet connection to use licensed features?**

A: No. License verification works offline. The license is validated locally using cryptographic signatures. You only need internet to activate the license initially.

---

### License Activation Issues

**Q: I get an "Invalid License Key" error. What should I do?**

A: Common causes:
- License key is incomplete (copy the entire key)
- Extra spaces before/after the key
- License has expired
- License is for a different installation (Installation ID mismatch)
- License was generated for a different organization

**Solution:** Copy the license key again carefully, verify you're using the correct installation, or contact support with your order details.

**Q: My license key won't paste into the activation field.**

A: Try these steps:
1. Copy the license key from the email
2. Paste into a text editor first (to remove formatting)
3. Copy from the text editor
4. Paste into the activation field

**Q: I activated my license but features are still locked.**

A: Try these steps:
1. Refresh your browser (Ctrl+F5 or Cmd+Shift+R)
2. Log out and log back in
3. Check the License Management page to verify activation
4. Contact support if the issue persists

---

### Feature Access

**Q: I purchased a feature but it's not showing in the UI.**

A: Ensure:
1. License is activated (check License Management page)
2. Feature is listed in your enabled features
3. Browser is refreshed
4. You're logged in with the correct account

**Q: Can I share my license with multiple organizations?**

A: No. Each license is tied to a specific installation using a unique Installation ID. This prevents license sharing and ensures each organization has their own valid license. You need separate licenses for each organization.

**Q: What is an Installation ID and how does it work?**

A: An Installation ID is a unique UUID automatically generated when your system is first installed. It serves as a digital fingerprint for your specific installation. When you purchase a license, it's cryptographically bound to this Installation ID, preventing unauthorized use on other installations.

**Q: Can I transfer my license to a different server?**

A: Yes. Licenses are tied to installations (via the database), not specific servers. If you migrate to a new server but keep the same database, your Installation ID remains the same and licenses continue to work. Contact support if you have issues after migration.

**Q: I'm getting an "Installation ID mismatch" error. What does this mean?**

A: This error occurs when trying to activate a license that was generated for a different installation. Each license is specifically bound to the Installation ID where it was purchased. This security feature prevents license sharing between organizations.

**Q: What happens when my license expires?**

A: When a license expires:
- You'll receive email notifications 30 days and 7 days before expiration
- On expiration, licensed features are immediately disabled
- Core features continue to work
- You can renew your license to restore features

---

### Billing and Renewals

**Q: How do I renew my license?**

A: You'll receive renewal reminders via email. Click the renewal link in the email or visit the pricing page to purchase a renewal. Activate the new license key when received.

**Q: Can I get a refund if I'm not satisfied?**

A: Please refer to our refund policy on the website or contact sales@yourdomain.com for refund requests.

**Q: Do you offer discounts for annual licenses?**

A: Yes! Annual licenses receive a discount compared to monthly pricing. See the pricing page for current offers.

**Q: Can I downgrade my license (remove features)?**

A: Yes. Contact support to discuss downgrading. You'll receive a new license key with fewer features. Refunds are subject to our refund policy.

---

### Technical Questions

**Q: Where is my license data stored?**

A: License information is stored locally in your installation's database. The license key itself is a cryptographically signed token that cannot be forged.

**Q: Is my license key secure?**

A: Yes. License keys are signed with RSA-256 encryption and cannot be modified or forged. They contain no sensitive information beyond your email and enabled features.

**Q: Can I transfer my license to a different server?**

A: Licenses are tied to installations, not servers. If you migrate to a new server, your license remains valid. Contact support if you have issues after migration.

**Q: What data is sent to the license server?**

A: No data is sent to any license server during normal operation. License verification happens entirely offline using cryptographic signatures. Data is only sent during the initial purchase and activation.

---

## Support

### Need Help?

If you encounter issues not covered in this guide:

- **Email Support:** support@yourdomain.com
- **Documentation:** https://docs.yourdomain.com
- **Community Forum:** https://community.yourdomain.com
- **Live Chat:** Available in the application (bottom-right corner)

### Include This Information

When contacting support about license issues, please provide:
- Your email address used for purchase
- Order/transaction ID
- Error messages (screenshots helpful)
- License status from License Management page
- Browser and operating system information

---

## Quick Reference

| Action | Location | Time Required |
|--------|----------|---------------|
| View license status | Settings → License | Instant |
| Activate license | Settings → License → Activate | 1 minute |
| Purchase features | License page → Purchase button | 5-10 minutes |
| Check trial remaining | Top banner or License page | Instant |
| Contact support | support@yourdomain.com | 24-48 hours response |

---

**Last Updated:** November 2025  
**Version:** 1.0
