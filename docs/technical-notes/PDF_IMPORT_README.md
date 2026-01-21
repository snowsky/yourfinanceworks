# PDF Import Feature

This document describes the new PDF import functionality that allows users to create invoices by uploading PDF files and automatically extracting invoice details using AI/LLM.

## 🚀 Features

### Two Invoice Creation Options

When creating a new invoice, users now see two options:

1. **📄 Import from PDF**
   - Upload a PDF invoice file
   - AI automatically extracts client information and invoice details
   - Creates client if they don't exist
   - Pre-populates invoice form with extracted data
   - Attaches original PDF for reference

2. **✏️ Create Manually**
   - Traditional manual invoice creation
   - Optional file attachment support
   - Full control over all invoice details

### Smart AI Integration

- **LLM Detection**: Automatically checks if AI/LLM is configured
- **Fallback Mode**: If LLM not available, proceeds with manual creation but keeps PDF attached
- **Multiple Model Support**: Works with Ollama models (llama2, mistral, gpt-oss, etc.)
- **Error Handling**: Graceful fallback to manual mode on processing errors

### Client Management

- **Auto-Detection**: Attempts to match extracted client info with existing clients
- **Auto-Creation**: Creates new clients automatically if they don't exist
- **Smart Matching**: Uses fuzzy matching to find similar client names

## 🛠️ Technical Implementation

### Backend Components

1. **PDF Processor API** (`api/routers/pdf_processor.py`)
   - `/api/v1/invoices/process-pdf` - Process PDF and extract data
   - `/api/v1/invoices/ai-status` - Check AI/LLM availability

2. **Enhanced Main Script** (`main.py`)
   - Command-line interface for PDF processing
   - JSON output support for API integration
   - Multiple model support

3. **Dependencies**
   - LangChain for PDF processing
   - Ollama for LLM integration
   - pypdf for PDF text extraction

### Frontend Components

1. **Invoice Creation Choice** (`ui/src/components/invoices/InvoiceCreationChoice.tsx`)
   - Two-option selection interface
   - File upload handling
   - AI status checking

2. **Enhanced Invoice Form** (`ui/src/components/invoices/InvoiceForm.tsx`)
   - Support for initial data from PDF
   - Attachment display
   - Pre-populated fields

3. **Updated New Invoice Page** (`ui/src/pages/NewInvoice.tsx`)
   - Choice component integration
   - PDF import handling
   - Client creation workflow

## 📋 Usage Instructions

### For Users

1. **Navigate to Create Invoice**
   - Go to Invoices → New Invoice
   - Choose between PDF import or manual creation

2. **PDF Import Process**
   - Click "Import from PDF"
   - Select a PDF file
   - Wait for processing (AI extracts data)
   - Review and edit extracted information
   - Save the invoice

3. **Manual Creation**
   - Click "Create Manually"
   - Optionally attach a file
   - Fill in all details manually
   - Save the invoice

### For Administrators

1. **AI Configuration**
   - Ensure Ollama is running (`ollama serve`)
   - Install required models (`ollama pull gpt-oss`)
   - Configure AI settings in Settings → AI Configuration

2. **Troubleshooting**
   - Check Ollama status: `curl http://localhost:11434/api/tags`
   - View API logs for processing errors
   - Test with sample PDF files

## 🔧 Setup Instructions

### Prerequisites

1. **Install Ollama**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Start Ollama service
   ollama serve
   
   # Pull a model
   ollama pull gpt-oss
   ```

2. **Install Python Dependencies**
   ```bash
   cd api
   pip install -r requirements.txt
   ```

### Configuration

1. **Environment Variables**
   ```bash
   # Add to .env file
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=gpt-oss
   ```

2. **Test Installation**
   ```bash
   # Run test script
   python test_pdf_import.py
   ```

## 🧪 Testing

### Manual Testing

1. **Test PDF Processing**
   ```bash
   python main.py --pdf-path sample.pdf --output-json
   ```

2. **Test API Endpoints**
   ```bash
   # Check AI status
   curl http://localhost:8000/api/v1/invoices/ai-status
   
   # Process PDF (requires multipart form data)
   curl -X POST -F "pdf_file=@sample.pdf" http://localhost:8000/api/v1/invoices/process-pdf
   ```

3. **Test UI Components**
   - Navigate to /invoices/new
   - Try both PDF import and manual creation
   - Verify file attachments work

### Automated Testing

Run the test script:
```bash
python test_pdf_import.py
```

## 📝 Data Flow

### PDF Import Flow

1. User selects PDF file
2. Frontend checks AI availability
3. PDF uploaded to backend
4. Backend processes PDF with LLM
5. Extracted data returned to frontend
6. Client matching/creation performed
7. Invoice form pre-populated
8. User reviews and saves invoice

### Data Structure

```json
{
  "invoice_data": {
    "date": "2024-01-15",
    "bills_to": "Client Name\nAddress",
    "items": [
      {
        "description": "Service/Product",
        "quantity": 1,
        "price": 100.00,
        "amount": 100.00,
        "discount": 0.0
      }
    ],
    "total_amount": 100.00,
    "total_discount": 0.0
  },
  "client_exists": false,
  "existing_client": null,
  "suggested_client": {
    "name": "Client Name",
    "address": "Full address from PDF"
  }
}
```

## 🚨 Error Handling

### Common Issues

1. **Ollama Not Running**
   - Error: "Ollama not available"
   - Solution: Start Ollama service

2. **Model Not Found**
   - Error: "Model not found"
   - Solution: Pull required model

3. **PDF Processing Timeout**
   - Error: "PDF processing timed out"
   - Solution: Use smaller PDF files or increase timeout

4. **Invalid PDF Format**
   - Error: "Only PDF files are supported"
   - Solution: Ensure file is valid PDF

### Fallback Behavior

- If AI processing fails, system automatically falls back to manual creation
- Original PDF is still attached for reference
- User can manually enter extracted information

## 🔒 Security Considerations

1. **File Upload Security**
   - Only PDF files accepted
   - File size limits enforced
   - Temporary files cleaned up

2. **AI Processing**
   - No sensitive data sent to external APIs (uses local Ollama)
   - PDF content processed locally
   - Extracted data validated before use

3. **Client Data**
   - Client matching uses fuzzy logic
   - No automatic overwrites of existing data
   - User confirmation required for new clients

## 🚀 Future Enhancements

1. **Multiple File Formats**
   - Support for images (JPG, PNG)
   - Support for Word documents
   - Support for Excel files

2. **Enhanced AI Features**
   - Better extraction accuracy
   - Multi-language support
   - Custom extraction rules

3. **Batch Processing**
   - Multiple PDF upload
   - Bulk invoice creation
   - Progress tracking

4. **Integration Options**
   - Email attachment processing
   - Cloud storage integration
   - API webhooks for automated processing

## 📞 Support

For issues or questions:

1. Check the troubleshooting section
2. Run the test script to verify setup
3. Check API logs for detailed error messages
4. Ensure all dependencies are installed correctly

---

**Note**: This feature requires Ollama to be running locally for AI processing. If Ollama is not available, the system will gracefully fall back to manual invoice creation with optional file attachments.