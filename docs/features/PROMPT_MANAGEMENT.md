# AI Prompt Management

YourFinanceWORKS features a centralized AI Prompt Management system that allows you to control, customize, and optimize the AI's behavior across the entire application. From complex invoice extraction to fraud detection audits, you have full control over the "instructions" the machine receives.

## 🚀 Key Features

- **Centralized Templates**: Manage all AI prompts (OCR, extraction, classification) from a single dashboard.
- **Jinja2 Support**: Use dynamic variables (e.g., `{{vendor}}`, `{{amount}}`) to inject contextual data into prompts.
- **Default with Override**: Ships with "Factory Defaults" for all features, which can be overridden at the tenant level for specific needs.
- **Provider-Specific Overrides**: Tailor prompts specifically for different AI models (OpenAI, Anthropic, etc.) for maximum performance.
- **Version Control**: Every change creates a new version. View history and restore previous versions with one click.
- **Usage Analytics**: Track successful executions, token consumption, and processing latency for every template.

## 🛠️ How it Works

The system follows a "Tiered Fallback" strategy to ensure high reliability:

1. **Database Lookup**: The system first checks for a custom version of the prompt configured by your organization.
2. **Factory Defaults**: If no custom version exists, it falls back to the robust, pre-configured defaults defined in our core library.
3. **Hardcoded Safety**: Legacy components include hardcoded fallbacks to ensure the app never fails due to a missing template.

## 📂 Managed Prompts

We manage prompts for every stage of the financial lifecycle:

| Feature Area          | Description                                            | Variables Used              |
| :-------------------- | :----------------------------------------------------- | :-------------------------- |
| **OCR Conversion**    | Converts raw receipt text into structured JSON.        | `raw_content`               |
| **Invoice Data**      | Identifies line items, tax rates, and totals.          | `text`                      |
| **Email AI**          | Classifies forwarded receipts and extracts data.       | `subject`, `body`, `sender` |
| **Forensic Auditing** | Identifies phantom vendors and description mismatches. | `vendor_name`, `amount`     |
| **Bank Statements**   | Maps text blocks to transaction tables.                | `text`                      |

## ⚙️ Management

Prompts are managed in the **Settings → AI Prompt Management** tab.

### 1. Editing Templates

You can modify the template content using Jinja2 syntax. This allows you to add specific instructions for your industry or language.

### 2. Testing

Before saving a new version, use the **Test Prompt** feature to verify the output with sample data.

### 3. Versions & Resets

If a customization isn't working as expected, you can:

- **Roll Back**: Revert to any previously saved version.
- **Factory Reset**: Revert the prompt to its original system state.

## 🔒 Security & Privacy

- **Data Isolation**: Custom prompts are stored in your private tenant database and are never shared across organizations.
- **Variable Sanitization**: Sensitive data is sanitized before being injected into prompt variables.
- **Audit Logs**: Every change to a prompt template is logged with the user's ID and a timestamp.

---

### Pro Tips

- **Model Tuning**: Some models respond better to specific keywords (e.g., "Think step by step"). Use **Provider Overrides** to optimize prompts for specific models.
- **JSON Enforcement**: Always include instructions for the AI to return "ONLY valid JSON" to ensure the application can parse the response correctly.

For technical architecture details, see the [Prompt System Guide](../technical-notes/PROMPT_SYSTEM_GUIDE.md).
