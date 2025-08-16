# Brand Guidelines - Invoice Management Application

## 🎨 **Color Palette**

### **Primary Colors**
- **Deep Navy**: `#3b82f6` (HSL: 221, 83%, 53%)
  - Use for: Primary buttons, links, main navigation
  - Conveys: Trust, professionalism, stability

- **Forest Green**: `#10b981` (HSL: 158, 64%, 52%)
  - Use for: Success states, positive amounts, completed actions
  - Conveys: Growth, prosperity, financial health

### **Accent Colors**
- **Gold**: `#f59e0b` (HSL: 43, 96%, 56%)
  - Use for: Premium features, highlights, warnings
  - Conveys: Premium quality, attention, value

- **Emerald**: `#10b981` (HSL: 160, 84%, 39%)
  - Use for: Success notifications, paid status
  - Conveys: Success, completion, positive outcomes

- **Rose**: `#f43f5e` (HSL: 0, 84%, 60%)
  - Use for: Error states, overdue invoices, destructive actions
  - Conveys: Urgency, attention required, caution

### **Neutral Colors**
- **Background**: `#fafafa` (Light) / `#0f172a` (Dark)
- **Foreground**: `#334155` (Light) / `#f8fafc` (Dark)
- **Muted**: `#f1f5f9` (Light) / `#1e293b` (Dark)
- **Border**: `#e2e8f0` (Light) / `#334155` (Dark)

## 🔤 **Typography**

### **Font Family**
- **Primary**: Inter (Google Fonts)
- **Fallback**: system-ui, -apple-system, sans-serif
- **Monospace**: JetBrains Mono, Fira Code, monospace

### **Font Weights**
- **Light**: 300 - For large headings, subtle text
- **Regular**: 400 - Body text, default weight
- **Medium**: 500 - Subheadings, emphasized text
- **Semibold**: 600 - Section headings, important labels
- **Bold**: 700 - Main headings, critical information

### **Font Sizes**
- **h1**: 2.5rem (40px) - Page titles
- **h2**: 2rem (32px) - Section headings
- **h3**: 1.5rem (24px) - Subsection headings
- **h4**: 1.25rem (20px) - Card titles
- **Body**: 1rem (16px) - Default text
- **Small**: 0.875rem (14px) - Captions, metadata
- **Tiny**: 0.75rem (12px) - Labels, badges

## 🎯 **Usage Guidelines**

### **Financial Status Colors**
```css
/* Paid Invoices */
.status-paid {
  background: emerald/10;
  color: emerald;
  border: emerald/20;
}

/* Pending Invoices */
.status-pending {
  background: gold/10;
  color: gold;
  border: gold/20;
}

/* Overdue Invoices */
.status-overdue {
  background: rose/10;
  color: rose;
  border: rose/20;
}

/* Partially Paid */
.status-partially-paid {
  background: navy/10;
  color: navy;
  border: navy/20;
}
```

### **Button Hierarchy**
- **Primary**: Navy background, white text - Main actions
- **Secondary**: Forest green background, white text - Positive actions
- **Outline**: Border with primary color, transparent background
- **Ghost**: No background, colored text - Subtle actions
- **Destructive**: Rose background, white text - Delete, cancel actions

### **Card Design**
- **Background**: White (light) / Dark card (dark mode)
- **Border**: Subtle border with rounded corners (0.5rem)
- **Shadow**: Soft shadow for elevation
- **Hover**: Slight shadow increase for interactivity

## 🌙 **Dark Mode**

### **Principles**
- Maintain color relationships and contrast ratios
- Use darker variants of primary colors
- Ensure text remains readable
- Preserve brand identity in dark theme

### **Color Adjustments**
- **Background**: Deep navy/black tones
- **Cards**: Slightly lighter than background
- **Text**: High contrast white/light gray
- **Borders**: Subtle dark borders for definition

## 📱 **Responsive Design**

### **Breakpoints**
- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px
- **Large**: > 1400px

### **Touch Targets**
- **Minimum**: 44px x 44px for touch elements
- **Preferred**: 48px x 48px for primary actions
- **Spacing**: 8px minimum between touch targets

## 🎨 **Component Styling**

### **Animations**
- **Duration**: 0.4s for most transitions
- **Easing**: cubic-bezier(0.4, 0, 0.2, 1) for smooth feel
- **Hover**: Subtle scale (1.02) or shadow changes
- **Loading**: Smooth pulse or spin animations

### **Spacing Scale**
- **xs**: 0.25rem (4px)
- **sm**: 0.5rem (8px)
- **md**: 1rem (16px)
- **lg**: 1.5rem (24px)
- **xl**: 2rem (32px)
- **2xl**: 3rem (48px)

## 🏢 **Brand Voice**

### **Tone**
- **Professional**: Trustworthy and reliable
- **Friendly**: Approachable and helpful
- **Clear**: Simple and easy to understand
- **Confident**: Authoritative without being intimidating

### **Language**
- Use clear, concise language
- Avoid jargon unless necessary
- Provide helpful context and guidance
- Maintain consistency in terminology

## ✅ **Implementation Checklist**

- [x] CSS variables defined in `index.css`
- [x] Tailwind config updated with brand colors
- [x] Inter font imported and configured
- [x] Status color utilities created
- [x] Animation improvements implemented
- [ ] Component library updated with new colors
- [ ] Dark mode thoroughly tested
- [ ] Accessibility compliance verified
- [ ] Brand guidelines documented

---

**Last Updated**: January 2025  
**Version**: 1.0  
**Status**: Implemented