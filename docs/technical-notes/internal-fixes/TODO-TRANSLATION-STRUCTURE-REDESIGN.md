# TODO: Translation Structure Redesign

## 📋 **Current Problem**

The current translation sync system (`mobile/scripts/sync-translations.js`) simply copies translation files from UI to mobile, but this approach has several limitations:

1. **Platform Differences**: UI and mobile have different UX patterns and space constraints
2. **Feature Divergence**: Mobile may have platform-specific features (camera, offline mode, gestures)
3. **Text Length**: Mobile needs shorter text due to screen size limitations
4. **Maintenance Issues**: Changes in UI automatically affect mobile without consideration

## 🎯 **Proposed Solution: Smart Translation Architecture**

### **New Directory Structure**
```
translations/
├── shared/           # Common translations for both platforms
│   ├── en.json       # Core business logic translations
│   ├── es.json       # (auth, invoices, clients, payments, etc.)
│   └── fr.json
├── ui-specific/      # Web-only translations  
│   ├── en.json       # (keyboard shortcuts, drag-drop, tooltips)
│   ├── es.json       # (advanced tables, modals, charts)
│   └── fr.json
└── mobile-specific/  # Mobile-only translations
    ├── en.json       # (gestures, camera, offline, navigation)
    ├── es.json       # (touch interactions, native features)
    └── fr.json
```

### **Smart Sync Process**
1. **Shared translations** contain core business functionality used by both platforms
2. **Platform-specific translations** contain UI/UX patterns unique to each platform
3. **Smart sync script** merges shared + platform-specific to generate final translation files

## 📊 **Translation Categories**

### **Shared Translations** (85% of content)
- ✅ Auth (login, signup, passwords)
- ✅ Business entities (invoices, clients, expenses, payments)
- ✅ Common actions (save, delete, edit, cancel)
- ✅ Status messages (success, error, warnings)
- ✅ Currency and formatting
- ✅ Dashboard metrics and analytics

### **UI-Specific Translations** (10% of content)
- 🖥️ Keyboard shortcuts ("Ctrl+S to save")
- 🖥️ Advanced table features (sorting, pagination)
- 🖥️ Drag & drop interactions
- 🖥️ Tooltips and hover states
- 🖥️ Modal window behaviors
- 🖥️ Complex form validations
- 🖥️ Bulk operations
- 🖥️ Chart and analytics exports

### **Mobile-Specific Translations** (5% of content)
- 📱 Touch gestures ("Pull to refresh", "Swipe to delete")
- 📱 Camera integration ("Take photo", "Scan receipt")
- 📱 Navigation patterns ("Menu", "Close", "Back")
- 📱 Offline functionality ("No connection", "Sync when online")
- 📱 File picker ("Select file", "Upload progress")
- 📱 Location services
- 📱 Push notifications

## 🛠️ **Implementation Plan**

### **Phase 1: Extract Shared Translations**
```bash
# 1. Create translation structure
mkdir -p translations/{shared,ui-specific,mobile-specific}

# 2. Extract common keys from current translations
# Identify shared keys (auth, invoices, clients, etc.)
# Move to translations/shared/
```

### **Phase 2: Identify Platform-Specific Keys**
```bash
# 3. Audit current UI translations for web-specific features
# Move UI-only keys to translations/ui-specific/

# 4. Audit mobile needs for mobile-specific features  
# Create mobile-only keys in translations/mobile-specific/
```

### **Phase 3: Create Smart Sync Script**
```javascript
// translations/smart-sync.js
// - Deep merge shared + platform-specific translations
// - Generate final files for ui/src/i18n/locales/ and mobile/src/i18n/locales/
// - Validation and error handling
// - Logging and statistics
```

### **Phase 4: Update Build Process**
```json
// package.json scripts update
{
  "sync-translations": "node translations/smart-sync.js",
  "build": "npm run sync-translations && npm run build:platform"
}
```

## 🎁 **Benefits of New Structure**

### **👨‍💻 Developer Experience**
- ✅ **Clear separation** of shared vs platform-specific content
- ✅ **No accidental overwrites** of platform-specific translations
- ✅ **Better maintainability** with organized, smaller files
- ✅ **Easier collaboration** between UI and mobile teams

### **🌐 Translation Management**
- ✅ **Reduce duplication** by sharing common translations
- ✅ **Platform optimization** with context-appropriate text
- ✅ **Consistent business terminology** across platforms
- ✅ **Flexible platform customization** when needed

### **🔄 Workflow Improvements**
- ✅ **Automated merging** eliminates manual sync errors
- ✅ **Validation checks** ensure translation completeness
- ✅ **Git-friendly** with smaller, focused diff changes
- ✅ **CI/CD integration** for automated translation builds

## 📝 **Example Translation Organization**

### **Shared (translations/shared/en.json)**
```json
{
  "auth": { "login": "Login", "email": "Email" },
  "invoices": { "title": "Invoices", "new": "New Invoice" },
  "common": { "save": "Save", "cancel": "Cancel" }
}
```

### **UI-Specific (translations/ui-specific/en.json)**
```json
{
  "ui": {
    "keyboard_shortcuts": { "save": "Ctrl+S to save" },
    "tables": { "sort_ascending": "Sort ascending" },
    "bulk_actions": { "select_all": "Select all items" }
  }
}
```

### **Mobile-Specific (translations/mobile-specific/en.json)**
```json
{
  "mobile": {
    "gestures": { "pull_to_refresh": "Pull to refresh" },
    "camera": { "take_photo": "Take Photo" },
    "navigation": { "menu": "Menu", "close_menu": "Close Menu" }
  }
}
```

### **Final Generated Files**
- **UI**: `shared` + `ui-specific` → `ui/src/i18n/locales/en.json`
- **Mobile**: `shared` + `mobile-specific` → `mobile/src/i18n/locales/en.json`

## ⚠️ **Migration Considerations**

### **Backward Compatibility**
- Ensure existing translation keys continue to work during migration
- Gradual migration strategy to avoid breaking changes
- Fallback mechanisms for missing platform-specific keys

### **Team Coordination**
- Update documentation for translation contributors
- Establish guidelines for shared vs platform-specific decisions
- Create review process for new translation keys

### **Testing Strategy**
- Automated tests for translation completeness
- Visual regression testing for text overflow issues
- Multi-language testing on both platforms

## 🚀 **Future Enhancements**

### **Advanced Features**
- **Dynamic translations**: Context-aware text based on user preferences
- **A/B testing**: Test different wording for better user engagement
- **Analytics integration**: Track which translations perform better
- **Auto-translation**: AI-powered translation suggestions for new keys

### **Tooling Improvements**
- **VS Code extension**: Syntax highlighting and validation for translation files
- **Web interface**: GUI for non-technical team members to manage translations
- **Integration APIs**: Connect with external translation services

## 📅 **Estimated Timeline**

- **Week 1**: Analysis and key extraction (Phase 1-2)
- **Week 2**: Smart sync script development (Phase 3)
- **Week 3**: Testing and build process integration (Phase 4)
- **Week 4**: Documentation and team training

## 📞 **Next Steps**

1. **Review and approve** this translation structure design
2. **Schedule implementation** when ready for larger changes
3. **Assign team members** for translation audit and extraction
4. **Plan migration strategy** to minimize disruption

---

**Status**: 📋 **TODO - Awaiting Review**  
**Priority**: 🔶 **Medium** (Quality of life improvement)  
**Impact**: 🎯 **High** (Better maintainability and platform optimization)

**Related Issues**:
- Current sync script overwrites mobile customizations
- Translation management becoming complex as platforms diverge
- Need for platform-specific UX optimizations
