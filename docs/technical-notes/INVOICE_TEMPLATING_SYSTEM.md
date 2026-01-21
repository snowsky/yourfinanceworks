# Invoice PDF Templating System

## Overview

The Invoice PDF Templating System allows customizable invoice layouts and styling without code changes. Users can select from predefined templates or create custom ones for different branding needs.

## Current Implementation

### Backend Components

- **`api/templates/invoice_templates.py`** - Template definitions and registry
- **`api/utils/pdf_generator.py`** - Enhanced PDF generator with template support

### Frontend Components

- **`ui/src/components/invoices/TemplateSelector.tsx`** - Template selection UI

### Available Templates

1. **Modern Template** - Blue color scheme, centered layout
2. **Classic Template** - Black color scheme, left-aligned layout

## Usage

### Backend
```python
# Generate PDF with specific template
pdf_bytes = generate_invoice_pdf(
    invoice_data, client_data, company_data,
    template_name='classic'
)
```

### Frontend
```tsx
<TemplateSelector 
  value={selectedTemplate} 
  onChange={setSelectedTemplate} 
/>
```

## Architecture

```
InvoiceTemplate (Abstract Base)
├── get_colors() -> Dict[str, Color]
└── get_layout() -> Dict[str, Any]

ModernTemplate extends InvoiceTemplate
ClassicTemplate extends InvoiceTemplate
```

## TODO: Template System Extensions

### High Priority
- [ ] **Logo Support** - Add company logo positioning and sizing
- [ ] **Font Selection** - Multiple font families per template
- [ ] **Layout Variants** - Single/multi-column layouts
- [ ] **Database Storage** - Store custom templates in database
- [ ] **Template Preview** - Live preview in UI before selection

### Medium Priority
- [ ] **Custom Field Positioning** - Configurable field placement
- [ ] **Color Customization** - User-defined color schemes
- [ ] **Multi-language Templates** - Localized template variants
- [ ] **Template Import/Export** - Share templates between tenants
- [ ] **Conditional Sections** - Show/hide sections based on data

### Low Priority
- [ ] **Advanced Layouts** - Complex multi-page layouts
- [ ] **Template Versioning** - Version control for template changes
- [ ] **Template Analytics** - Track template usage statistics
- [ ] **Template Marketplace** - Community template sharing
- [ ] **Dynamic Templates** - AI-generated templates based on industry

### Technical Improvements
- [ ] **Template Validation** - Validate template configuration
- [ ] **Performance Optimization** - Cache compiled templates
- [ ] **Error Handling** - Graceful fallback for invalid templates
- [ ] **Unit Tests** - Comprehensive template testing
- [ ] **Documentation** - Template creation guide

## Implementation Notes

- Templates are lightweight and focus on styling/layout only
- PDF generation logic remains unchanged
- Easy to extend with new template types
- Backward compatible with existing invoices
- No database migrations required for basic templates

## Future Considerations

- Consider moving to JSON-based template definitions for non-developers
- Evaluate template editor UI for advanced customization
- Plan for mobile app template support
- Consider integration with brand management systems