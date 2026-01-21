# Barcode Scanning - Quick Start Guide

## Installation

### Web UI
```bash
cd ui
npm install
npm run dev
```

### Mobile App
```bash
cd mobile
npm install
npm start
```

## Testing with IKEA Barcode

1. **Get an IKEA product barcode** (any product with a barcode)
2. **Create an inventory item** with that barcode:
   - Go to Inventory → Add Item
   - Enter product name, price, etc.
   - Assign the IKEA barcode to the item
3. **Test the scanner**:
   - Click "Scan Barcode" button
   - Point camera at the IKEA barcode
   - System will detect and display the item

## Web UI Usage

### Camera Scanning
1. Click "Scan Barcode" button in Inventory page
2. Click "Start Camera Scan"
3. Point camera at barcode
4. System automatically detects and looks up item

### Manual Entry
1. Click "Scan Barcode" button
2. Type barcode number in "Manual Entry" section
3. Click "Lookup Barcode"

## Mobile App Usage

### Camera Scanning
1. Open Inventory screen
2. Tap blue barcode button (top right)
3. Point camera at barcode
4. System automatically detects and displays item

### Manual Entry
1. Tap barcode button
2. Scroll down to "Or enter manually"
3. Type barcode number
4. Tap "Lookup Barcode"

## Supported Barcode Formats

### Web (Quagga2)
- UPC-A (12 digits)
- UPC-E (8 digits)
- EAN-13 (13 digits)
- EAN-8 (8 digits)
- Code 128
- Code 39
- Codabar

### Mobile (Expo Barcode Scanner)
- UPC-A, UPC-E
- EAN-13, EAN-8
- Code 128, Code 39
- QR Code
- PDF417
- Aztec

## Troubleshooting

### Camera Not Working
- **Web**: Check browser permissions, ensure HTTPS (except localhost)
- **Mobile**: Grant camera permission in device settings
- **Fallback**: Use manual entry instead

### Barcode Not Detected
- Ensure good lighting
- Hold barcode steady for 1-2 seconds
- Try different angles
- Use manual entry as fallback

### Item Not Found
- Verify barcode is assigned to an inventory item
- Check barcode format is correct
- Try looking up item manually in inventory list

## API Endpoints Used

```
POST /inventory/barcode/validate
GET /inventory/items/barcode/{barcode}
```

## Next Steps

1. Install dependencies: `npm install` in both `ui/` and `mobile/`
2. Test with a real barcode (IKEA or any product)
3. Create inventory items with barcodes
4. Start scanning!

## Performance Tips

- **Web**: Works best on modern browsers (Chrome, Firefox)
- **Mobile**: Native app provides better performance than web
- **Lighting**: Good lighting improves detection speed
- **Barcode Quality**: Clear, undamaged barcodes scan faster
