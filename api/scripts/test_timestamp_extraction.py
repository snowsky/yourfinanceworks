#!/usr/bin/env python3
"""
Test script for receipt timestamp extraction functionality
"""
import sys
import os
import asyncio
from datetime import datetime, timezone

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commercial.ai.services.ocr_service import _heuristic_parse_text, _extract_json_from_text


def test_timestamp_extraction():
    """Test timestamp extraction from sample receipt text"""
    
    print("🧪 Testing Receipt Timestamp Extraction")
    print("=" * 50)
    
    # Sample receipt texts with various timestamp formats
    test_receipts = [
        {
            "name": "Standard Receipt with Time",
            "text": """
            WALMART SUPERCENTER
            123 MAIN ST
            ANYTOWN, ST 12345
            
            Date: 2024-11-06
            Time: 14:32
            
            GROCERIES
            Milk                $3.99
            Bread               $2.49
            Total:              $6.48
            
            Thank you for shopping!
            """
        },
        {
            "name": "Receipt with AM/PM Time",
            "text": """
            TARGET STORE #1234
            456 ELM STREET
            
            11/06/2024  2:45 PM
            
            HOUSEHOLD ITEMS
            Detergent          $12.99
            Paper Towels        $8.49
            
            Subtotal:          $21.48
            Tax:                $1.72
            Total:             $23.20
            """
        },
        {
            "name": "Receipt with Date/Time Combined",
            "text": """
            STARBUCKS COFFEE
            Store #5678
            
            2024-11-06 08:15:30
            
            Grande Latte        $5.45
            Blueberry Muffin    $3.25
            
            Total:              $8.70
            Card Payment
            """
        },
        {
            "name": "Receipt with Only Date (No Time)",
            "text": """
            BEST BUY
            Electronics Store
            
            Purchase Date: 11/06/2024
            
            USB Cable          $19.99
            Screen Protector   $14.99
            
            Subtotal:          $34.98
            Tax:                $2.80
            Total:             $37.78
            """
        },
        {
            "name": "Receipt with European Time Format",
            "text": """
            TESCO EXPRESS
            London, UK
            
            06/11/2024 16:22
            
            Sandwich            £3.50
            Crisps              £1.25
            Drink               £1.80
            
            Total:              £6.55
            """
        }
    ]
    
    print(f"Testing {len(test_receipts)} sample receipts...\n")
    
    for i, receipt in enumerate(test_receipts, 1):
        print(f"📄 Test {i}: {receipt['name']}")
        print("-" * 30)
        
        # Test heuristic parsing
        result = _heuristic_parse_text(receipt['text'])
        
        if result:
            print("✅ Extraction Results:")
            for key, value in result.items():
                print(f"   {key}: {value}")
            
            # Check if timestamp was extracted
            if 'receipt_timestamp' in result:
                print(f"🕐 Timestamp extracted: {result['receipt_timestamp']}")
                
                # Try to parse the timestamp
                try:
                    from dateutil import parser as dateparser
                    parsed_dt = dateparser.parse(result['receipt_timestamp'])
                    print(f"✅ Parsed timestamp: {parsed_dt}")
                    print(f"   Hour: {parsed_dt.hour}")
                    print(f"   Day of week: {parsed_dt.strftime('%A')}")
                except Exception as e:
                    print(f"❌ Failed to parse timestamp: {e}")
            else:
                print("⚠️  No timestamp extracted")
        else:
            print("❌ No data extracted")
        
        print()
    
    print("🎯 Testing JSON Extraction")
    print("-" * 30)
    
    # Test JSON extraction with timestamp
    json_text = '''
    Here is the extracted data:
    {
        "amount": 25.99,
        "currency": "USD",
        "expense_date": "2024-11-06",
        "receipt_timestamp": "2024-11-06 14:30:00",
        "category": "Food",
        "vendor": "McDonald's",
        "total_amount": 25.99
    }
    Additional text here...
    '''
    
    json_result = _extract_json_from_text(json_text)
    if json_result:
        print("✅ JSON Extraction Results:")
        for key, value in json_result.items():
            print(f"   {key}: {value}")
        
        if 'receipt_timestamp' in json_result:
            print(f"🕐 JSON Timestamp: {json_result['receipt_timestamp']}")
    else:
        print("❌ No JSON extracted")
    
    print("\n" + "=" * 50)
    print("✅ Timestamp extraction testing completed!")


async def test_full_ocr_pipeline():
    """Test the full OCR pipeline with timestamp extraction"""
    print("\n🔄 Testing Full OCR Pipeline")
    print("=" * 50)
    
    # This would require an actual image file and AI service
    # For now, just demonstrate the expected flow
    
    sample_ocr_result = {
        "amount": 15.99,
        "currency": "USD",
        "expense_date": "2024-11-06",
        "receipt_timestamp": "2024-11-06 12:45:00",
        "category": "Lunch",
        "vendor": "Subway",
        "tax_amount": 1.28,
        "total_amount": 17.27,
        "payment_method": "Credit Card"
    }
    
    print("📊 Sample OCR Result with Timestamp:")
    for key, value in sample_ocr_result.items():
        print(f"   {key}: {value}")
    
    # Simulate timestamp processing
    if 'receipt_timestamp' in sample_ocr_result:
        try:
            from dateutil import parser as dateparser
            timestamp = dateparser.parse(sample_ocr_result['receipt_timestamp'])
            
            print(f"\n🕐 Timestamp Analysis:")
            print(f"   Parsed: {timestamp}")
            print(f"   Hour: {timestamp.hour} ({timestamp.strftime('%I:%M %p')})")
            print(f"   Day: {timestamp.strftime('%A')}")
            print(f"   Date: {timestamp.strftime('%Y-%m-%d')}")
            
            # Simulate expense habit insights
            if 11 <= timestamp.hour <= 14:
                print(f"💡 Insight: This appears to be a lunch expense")
            elif 6 <= timestamp.hour <= 10:
                print(f"💡 Insight: This appears to be a breakfast expense")
            elif 17 <= timestamp.hour <= 21:
                print(f"💡 Insight: This appears to be a dinner expense")
            else:
                print(f"💡 Insight: This is an off-hours purchase")
                
        except Exception as e:
            print(f"❌ Timestamp processing failed: {e}")


def main():
    """Main test function"""
    print("🚀 Receipt Timestamp Extraction Test Suite")
    print("=" * 60)
    
    # Test heuristic parsing
    test_timestamp_extraction()
    
    # Test full pipeline simulation
    asyncio.run(test_full_ocr_pipeline())
    
    print("\n🎉 All tests completed!")
    print("\nNext steps:")
    print("1. Upload a receipt image to test real OCR extraction")
    print("2. Check the expense analytics endpoints:")
    print("   - GET /api/v1/expense-analytics/spending-patterns")
    print("   - GET /api/v1/expense-analytics/category-timing")
    print("   - GET /api/v1/expense-analytics/extraction-stats")


if __name__ == "__main__":
    main()