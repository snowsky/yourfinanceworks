# FinanceWorks Insights (AI Forensic Auditor)

FinanceWorks Insights is an advanced, AI-powered oversight system that acts as a **Senior Forensic Auditor** for your organization. It proactively monitors every invoice, expense, and bank transaction for anomalies, potential fraud, and documentation errors.

## 🚀 Key Features

- **Automated Audit Stream**: Every financial document is automatically analyzed against a suite of forensic rules the moment it's processed.
- **Risk Scoring**: Each transaction receives a risk score (0-100) and a risk level (Low, Medium, High) based on detected anomalies.
- **Forensic Reasoning**: Instead of just flagging a document, the system provides a detailed explanation of _why_ something was flagged.
- **Proactive Fraud Detection**: Protects against common embezzlement and error patterns like "Phantom Vendors" and "Threshold Splitting."
- **Attachment Integrity**: Analyzes receipts and invoices for signs of digital tampering or formatting inconsistencies.

## 🛠️ Detection Rules

Our "Senior Auditor" persona applies several specialized rules to your data:

| Rule Name                | Description                                                                                             | What it protects against                             |
| :----------------------- | :------------------------------------------------------------------------------------------------------ | :--------------------------------------------------- |
| **Phantom Vendor**       | Identifies vendors with suspicious names or typos of major brands.                                      | Fictitious entities used to siphon funds.            |
| **Duplicate Billing**    | Detects multiple submissions of the same invoice or receipt.                                            | Double payments and accidental overcharging.         |
| **Threshold Splitting**  | Flags cases where large expenses are broken into smaller ones to bypass approval limits.                | Policy circumvention.                                |
| **Rounding Anomaly**     | Flags perfectly round numbers (e.g., $1,000.00) in high-value transactions.                             | Falsified documentation or lack of precise receipts. |
| **Description Mismatch** | Identifies items that don't match the vendor's primary business (e.g., "Watch" from "Office Supplies"). | Personal purchases hidden as business expenses.      |
| **Temporal Anomaly**     | Detects transactions occurring at unusual times (e.g., Sunday at 3 AM).                                 | Unauthorized or suspicious activity.                 |

## ⚙️ How it Works

The Insights engine runs in the background and integrates directly with your workflow:

1. **Ingestion**: A document is uploaded or a transaction is imported.
2. **Modular Audit**: The system runs all active forensic rules against the data and attachments.
3. **Flagging**: If an anomaly is found, a red 🚩 flag appears on the document in the UI.
4. **Review**: Administrators and Approvers can click the flag to see the "Auditor's Notes" and risk assessment.

## 🛡️ Governance & Settings

- **Enterprise Oversight**: FinanceWorks Insights requires an Enterprise-tier license and is enabled globally via the **Settings → AI Configuration** menu.
- **Audit Logs**: Every audit result is permanently logged, creating a defensible paper trail for external auditors.
- **Reprocessing**: Administrators can trigger a "Full System Audit" to re-evaluate historical data if policies change.

---

### Pro Tips

- **Check Medium Risks**: Don't just focus on "High" risks. Rounding anomalies often point to process issues rather than direct fraud.
- **Persona Context**: The AI "Auditor" is trained on thousands of known fraud patterns, making it highly effective at spotting subtle formatting oddities in receipts.

For a technical overview of the detection engine, see the [Anomaly Detection implementation](../technical-notes/README.md).
