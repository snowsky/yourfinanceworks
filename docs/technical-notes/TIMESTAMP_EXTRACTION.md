# Receipt Timestamp Extraction for Expense Habit Analytics

This document describes the receipt timestamp extraction functionality that enables detailed expense habit analytics based on the exact time purchases were made.

## Overview

The system now extracts precise timestamps from receipt images using OCR technology, allowing for comprehensive analysis of spending patterns by:
- Time of day (hourly patterns)
- Day of week (weekly patterns)
- Monthly trends
- Category-specific timing insights

## Features

### 1. Timestamp Extraction
- **OCR Enhancement**: Updated OCR prompts to specifically extract receipt timestamps
- **Multiple Formats**: Supports various timestamp formats (24-hour, 12-hour AM/PM, combined date-time)
- **Heuristic Parsing**: Fallback parsing for plain text OCR results
- **Validation**: Robust timestamp parsing with error handling

### 2. Database Schema
New fields added to the `expenses` table:
- `receipt_timestamp`: Exact timestamp from receipt (DateTime with timezone)
- `receipt_time_extracted`: Boolean flag indicating successful extraction

### 3. Analytics Service
Comprehensive analytics service (`ExpenseAnalyticsService`) providing:

#### Spending Patterns Analysis
- Hourly spending distribution (0-23 hours)
- Daily spending patterns (Monday-Sunday)
- Monthly spending trends
- Peak spending times identification

#### Frequency Analysis
- Transaction frequency by time periods
- Percentage distribution of purchases
- Most active spending times

#### Category Timing Insights
- When different expense categories are typically purchased
- Category-specific peak hours and days
- Spending behavior patterns by category

#### Extraction Statistics
- Success rate of timestamp extraction
- Number of expenses with/without timestamps
- Analytics availability status

### 4. API Endpoints

All endpoints are available under `/api/v1/expense-analytics/`:

#### GET `/spending-patterns`
Analyze spending patterns by time periods.

**Query Parameters:**
- `start_date` (optional): Start date for analysis (YYYY-MM-DD)
- `end_date` (optional): End date for analysis (YYYY-MM-DD)

**Response:**
```json
{
  "total_expenses": 45,
  "total_amount": 1250.75,
  "average_amount": 27.79,
  "hourly_spending": [
    {"hour": 0, "amount": 0},
    {"hour": 12, "amount": 245.50},
    ...
  ],
  "daily_spending": [
    {"day": 0, "day_name": "Monday", "amount": 180.25},
    ...
  ],
  "peak_times": {
    "hour": {"hour": 12, "amount": 245.50},
    "day": {"day": 5, "day_name": "Saturday", "amount": 320.75}
  }
}
```

#### GET `/spending-frequency`
Analyze how often purchases are made at different times.

**Response:**
```json
{
  "total_transactions": 45,
  "hourly_frequency": [
    {"hour": 12, "count": 8, "percentage": 17.8},
    ...
  ],
  "most_active": {
    "hour": {"hour": 12, "count": 8},
    "day": {"day": 5, "day_name": "Saturday", "count": 12}
  }
}
```

#### GET `/category-timing`
Analyze when different expense categories are purchased.

**Response:**
```json
{
  "total_categories": 5,
  "categories": [
    {
      "category": "Food",
      "transaction_count": 20,
      "total_amount": 450.25,
      "peak_hour": {"hour": 12, "count": 8, "percentage": 40},
      "peak_day": {"day": 5, "day_name": "Saturday", "count": 6}
    }
  ]
}
```

#### GET `/extraction-stats`
Get statistics about timestamp extraction success.

**Response:**
```json
{
  "total_expenses": 100,
  "expenses_with_attachments": 75,
  "expenses_with_timestamps": 60,
  "timestamp_extraction_success_rate": 80.0,
  "analytics_available": true
}
```

#### GET `/summary`
Get comprehensive analytics summary for a specified period.

**Query Parameters:**
- `days` (optional): Number of days to analyze (default: 30)

## Usage Examples

### 1. Upload Receipt with Timestamp
When uploading a receipt image, the OCR system will automatically:
1. Extract expense details (amount, vendor, etc.)
2. Look for timestamp information on the receipt
3. Parse and store the exact purchase time
4. Set `receipt_time_extracted = true` if successful

### 2. Analyze Spending Habits
```bash
# Get spending patterns for the last 30 days
curl -X GET "/api/v1/expense-analytics/spending-patterns" \
  -H "Authorization: Bearer <token>"

# Get category timing insights
curl -X GET "/api/v1/expense-analytics/category-timing?start_date=2024-10-01&end_date=2024-10-31" \
  -H "Authorization: Bearer <token>"
```

### 3. View Analytics Dashboard
The extracted timestamps enable insights like:
- "You spend most on groceries on Saturday afternoons"
- "Your coffee purchases peak at 8 AM on weekdays"
- "Dinner expenses are highest on Friday evenings"

## Supported Timestamp Formats

The system recognizes various timestamp formats commonly found on receipts:

### Date Formats
- `2024-11-06` (ISO format)
- `11/06/2024` (US format)
- `06/11/2024` (European format)
- `Nov 6, 2024` (Text format)

### Time Formats
- `14:32` (24-hour format)
- `2:45 PM` (12-hour with AM/PM)
- `08:15:30` (with seconds)
- `16:22` (European 24-hour)

### Combined Formats
- `2024-11-06 14:32:00`
- `11/06/2024 2:45 PM`
- `06/11/2024 16:22`

## Implementation Details

### OCR Enhancement
The OCR prompts have been updated to specifically request timestamp extraction:

```python
prompt = (
    "Extract key expense fields and respond ONLY with compact JSON. "
    "Required keys: amount, currency, expense_date (YYYY-MM-DD), "
    "category, vendor, receipt_timestamp (YYYY-MM-DD HH:MM:SS if available). "
    "For receipt_timestamp, extract the exact time from the receipt if visible."
)
```

### Heuristic Parsing
For plain text OCR results, the system uses regex patterns to find timestamps:

```python
# Time patterns like HH:MM, H:MM AM/PM
m_time = re.search(r"(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)", text)
```

### Database Migration
Run the migration to add timestamp fields:

```bash
cd api
alembic upgrade head
```

## Testing

Run the test script to verify timestamp extraction:

```bash
cd api
python scripts/test_timestamp_extraction.py
```

This will test various receipt formats and demonstrate the extraction capabilities.

## Benefits for Users

1. **Detailed Insights**: Understand exactly when spending occurs
2. **Habit Analysis**: Identify patterns in purchasing behavior
3. **Budget Planning**: Plan expenses based on historical timing patterns
4. **Category Optimization**: Optimize shopping times for different categories
5. **Trend Detection**: Spot changes in spending habits over time

## Future Enhancements

Potential improvements for timestamp extraction:
1. **Time Zone Support**: Handle receipts from different time zones
2. **Confidence Scoring**: Rate the confidence of timestamp extraction
3. **Manual Correction**: Allow users to manually correct extracted timestamps
4. **Advanced Analytics**: Machine learning for spending prediction
5. **Comparative Analysis**: Compare spending patterns across time periods