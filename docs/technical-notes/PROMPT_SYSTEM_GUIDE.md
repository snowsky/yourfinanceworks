# Prompt System Guide

This document explains the architecture and usage of the AI Prompt System in the Invoice App.

## Overview

The Prompt System allows for centralized management, versioning, and customization of AI prompts used throughout the application (e.g., invoice extraction, expense categorization, OCR conversion).

It is designed with a "Default with Override" philosophy:
1.  **Defaults**: The system ships with robust default templates defined in code.
2.  **Overrides**: Tenants can customize these prompts in the database to suit their specific needs without code changes.
3.  **Fallbacks**: If a database record is missing, the system robustly falls back to the code-defined default.

## Architecture

### 1. Default Templates
Core prompts are defined in `api/core/constants/default_prompts.py`. This is the source of truth for the system's "factory settings".

Current defaults include:
*   `pdf_invoice_extraction`: For processing PDF text.
*   `invoice_processing`: For general structured invoice data.
*   `receipt_processing`: For receipt data extraction.
*   `expense_categorization`: For categorizing expenses.
*   `ocr_data_conversion`: For converting raw OCR output to JSON.

### 2. Fallback Logic (`PromptService`)
The `PromptService.get_prompt()` method implements a tiered resolution strategy:

1.  **Database Lookup**: Checks the tenant's database for a custom version of the prompt.
2.  **Default Template**: If not found in DB, it loads the definition from `default_prompts.py`.
3.  **Hardcoded Fallback**: (Legacy) Code usage sites may provide a fallback string, but this is now secondary to the centralized defaults.

This ensures that even if the database is empty (e.g., fresh install, failed seed), the application functions correctly using the shipped defaults.

## Configuration & Customization

### Database Seeding
When a new tenant is created, the `TenantDatabaseManager` seeds the `prompt_templates` table with the defaults. This allows immediate customization.

### UI Management
Prompts can be managed via the User Interface:
*   **Location**: **Settings > Prompts** (or navigate to `/prompts`)
*   **Features**:
    *   **Edit**: Modify the template content (Jinja2 syntax).
    *   **Reset**: Revert a prompt to its factory default state.
    *   **Test**: Run a prompt with sample variables to verify output.
    *   **Versions**: View and restore previous versions of a prompt.

## Naming Convention
To customize a specific system behavior, you must use the correct internal name:

| UI Name / Description | Internal Name (`name`) | Usage |
| :--- | :--- | :--- |
| PDF Invoice Extraction | `pdf_invoice_extraction` | `pdf_processor.py` |
| OCR Data Conversion | `ocr_data_conversion` | `ocr_service.py` |
| Invoice Processing | `invoice_processing` | General invoice AI |
| Receipt Processing | `receipt_processing` | Receipt AI |
| Expense Categorization | `expense_categorization` | Expense AI |

## Adding New Prompts
To add a new system prompt:
1.  Add the definition to `api/core/constants/default_prompts.py`.
2.  The system will automatically recognize it as a valid fallback.
3.  (Optional) New tenants will get it seeded automatically. Existing tenants will use the fallback until explicitly created/customized.
