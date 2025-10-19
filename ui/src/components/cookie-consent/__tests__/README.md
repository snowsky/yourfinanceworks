# Cookie Consent Banner - Comprehensive Test Suite

This directory contains a comprehensive test suite for the Cookie Consent Banner component, ensuring GDPR compliance, accessibility standards, and cross-browser compatibility.

## 📋 Test Suite Overview

The test suite is organized into six main categories, each targeting specific aspects of the component:

### 1. Basic Comprehensive Tests (`comprehensive/BasicTestSuite.test.tsx`)
- **Purpose**: Core functionality validation
- **Coverage**: End-to-end flows, GDPR basics, accessibility basics, error handling
- **Requirements**: 4.1, 5.1, 5.2, 5.3, 5.4
- **Runtime**: ~500ms

### 2. End-to-End User Flow Tests (`e2e/CookieConsentE2E.test.tsx`)
- **Purpose**: Complete user journey validation
- **Coverage**: Accept all flow, custom preferences flow, keyboard navigation
- **Requirements**: 1.1, 2.1, 3.1, 6.3
- **Runtime**: ~3000ms

### 3. Accessibility Compliance Tests (`accessibility/AccessibilityCompliance.test.tsx`)
- **Purpose**: WCAG 2.1 AA compliance validation
- **Coverage**: ARIA attributes, keyboard navigation, screen reader support
- **Requirements**: 4.1, 4.2, 4.3, 4.4, 4.5
- **Runtime**: ~2000ms

### 4. GDPR Compliance Tests (`gdpr/GDPRCompliance.test.tsx`)
- **Purpose**: Legal compliance validation
- **Coverage**: Consent requirements, withdrawal rights, record keeping
- **Requirements**: 5.1, 5.2, 5.3, 5.4
- **Runtime**: ~2500ms

### 5. Cross-Browser Compatibility Tests (`cross-browser/CrossBrowserCompatibility.test.tsx`)
- **Purpose**: Browser compatibility validation
- **Coverage**: Chrome, Firefox, Safari, Edge, IE11, mobile browsers
- **Requirements**: 7.1, 7.2, 7.4
- **Runtime**: ~1500ms

### 6. Comprehensive Integration Tests (`comprehensive/ComprehensiveTestSuite.test.tsx`)
- **Purpose**: Integration and stress testing
- **Coverage**: Real-world scenarios, performance, memory management
- **Requirements**: All requirements
- **Runtime**: ~4000ms

## 🚀 Running Tests

### Run All Test Suites
```bash
# Run the comprehensive test runner
node ui/src/components/cookie-consent/__tests__/run-comprehensive-tests.js

# Or run individual suites
npm test -- --run src/components/cookie-consent/__tests__/comprehensive/BasicTestSuite.test.tsx
```

### Run Specific Test Categories
```bash
# Basic functionality only
npm test -- --run src/components/cookie-consent/__tests__/comprehensive/BasicTestSuite.test.tsx

# Accessibility compliance only  
npm test -- --run src/components/cookie-consent/__tests__/accessibility/AccessibilityCompliance.test.tsx

# GDPR compliance only
npm test -- --run src/components/cookie-consent/__tests__/gdpr/GDPRCompliance.test.tsx
```

## 📊 Requirements Coverage

The test suite covers all requirements from the specification:

### User Interface Requirements (1.x)
- ✅ 1.1: Display consent banner on first visit
- ✅ 1.2: Show clear cookie usage message
- ✅ 1.3: Include Accept All and Manage Preferences buttons
- ✅ 1.4: Fixed bottom positioning
- ✅ 1.5: Responsive mobile design

### Accept All Flow Requirements (2.x)
- ✅ 2.1: Store consent in localStorage on Accept All
- ✅ 2.2: Hide banner after consent given
- ✅ 2.3: Set cookieConsent key to 'accepted'
- ✅ 2.4: Enable analytics and marketing scripts
- ✅ 2.5: No banner on subsequent visits

### Preferences Management Requirements (3.x)
- ✅ 3.1: Open preferences modal on Manage Preferences click
- ✅ 3.2: Display three cookie categories
- ✅ 3.3: Allow independent toggle of Analytics and Marketing
- ✅ 3.4: Store custom preferences on save
- ✅ 3.5: Store individual category preferences

### Accessibility Requirements (4.x)
- ✅ 4.1: ARIA labels and roles for screen readers
- ✅ 4.2: Full keyboard navigation support
- ✅ 4.3: Focus trapping within modal
- ✅ 4.4: High contrast ratios (4.5:1 minimum)
- ✅ 4.5: Clear focus indicators

### GDPR Compliance Requirements (5.x)
- ✅ 5.1: No non-essential cookies until consent
- ✅ 5.2: Only essential cookies by default
- ✅ 5.3: Clear cookie category information
- ✅ 5.4: Consent withdrawal capability

### Analytics Integration Requirements (6.x)
- ✅ 6.1: JavaScript API for consent status
- ✅ 6.2: Analytics script loading on consent
- ✅ 6.3: Event callbacks for consent changes
- ✅ 6.4: Framework integration examples
- ✅ 6.5: Custom analytics provider support

### Design Requirements (7.x)
- ✅ 7.1: Light and dark mode themes
- ✅ 7.2: Customizable primary color
- ✅ 7.3: Smooth show/hide animations
- ✅ 7.4: Consistent styling across screen sizes
- ✅ 7.5: Modern design elements

## 🔍 Test Categories

### Functionality Tests
- Component rendering and state management
- User interaction handling
- Consent storage and retrieval
- Analytics integration

### GDPR Compliance Tests
- Lawful basis for processing
- Consent withdrawal rights
- Record keeping requirements
- Data subject rights

### Accessibility Tests
- WCAG 2.1 AA compliance
- Screen reader compatibility
- Keyboard navigation
- Color contrast validation
- Focus management

### Cross-Browser Tests
- Chrome, Firefox, Safari, Edge compatibility
- IE11 polyfill support
- Mobile browser testing
- Storage fallback mechanisms

### Performance Tests
- Memory leak prevention
- Rapid interaction handling
- Animation performance
- Component cleanup

### Error Handling Tests
- localStorage unavailable scenarios
- Quota exceeded errors
- Network failures
- Component error boundaries

## 🛠️ Test Infrastructure

### Mocking Strategy
- **localStorage**: Comprehensive mocking with error scenarios
- **matchMedia**: Theme and responsive behavior testing
- **DOM APIs**: Script loading and event handling
- **Analytics**: Safe testing without external dependencies

### Test Utilities
- **User Events**: Realistic user interaction simulation
- **Accessibility Testing**: ARIA attribute validation
- **Performance Monitoring**: Memory and timing validation
- **Error Simulation**: Graceful degradation testing

### Browser Simulation
- **User Agent Mocking**: Different browser identification
- **Feature Detection**: CSS and JavaScript capability testing
- **Storage Behavior**: Browser-specific localStorage quirks
- **Event Handling**: Cross-browser event compatibility

## 📈 Quality Metrics

### Test Coverage Goals
- **Functionality**: 100% of user-facing features
- **GDPR Compliance**: 100% of legal requirements
- **Accessibility**: 100% of WCAG 2.1 AA criteria
- **Browser Support**: 95% of target browsers
- **Error Scenarios**: 90% of failure modes

### Performance Benchmarks
- **Test Execution**: < 15 seconds total
- **Memory Usage**: No memory leaks detected
- **Component Rendering**: < 100ms initial render
- **Animation Performance**: 60fps target

## 🚨 Known Limitations

### Test Environment Constraints
- **Real Browser Testing**: Tests run in jsdom, not real browsers
- **Network Requests**: Analytics scripts are mocked, not loaded
- **Timing Dependencies**: Some animations may behave differently
- **Screen Reader Testing**: ARIA validation only, not actual screen reader testing

### Recommended Additional Testing
- **Manual Testing**: Real browser validation
- **Screen Reader Testing**: NVDA, JAWS, VoiceOver validation
- **Performance Testing**: Real-world performance monitoring
- **Legal Review**: GDPR compliance verification by legal experts

## 📝 Contributing

When adding new tests:

1. **Follow Naming Conventions**: Use descriptive test names
2. **Add Requirements Mapping**: Reference specific requirements
3. **Include Error Scenarios**: Test both success and failure paths
4. **Document Test Purpose**: Clear descriptions of what's being tested
5. **Update Coverage**: Add new requirements to the coverage matrix

### Test File Structure
```
__tests__/
├── comprehensive/          # Core functionality tests
├── e2e/                   # End-to-end user flow tests
├── accessibility/         # WCAG compliance tests
├── gdpr/                 # Legal compliance tests
├── cross-browser/        # Browser compatibility tests
└── README.md             # This documentation
```

## 🔗 Related Documentation

- [Cookie Consent Banner Requirements](../requirements.md)
- [Cookie Consent Banner Design](../design.md)
- [Cookie Consent Banner Tasks](../tasks.md)
- [Component API Documentation](../README.md)
- [GDPR Compliance Guide](../docs/gdpr-compliance.md)
- [Accessibility Guide](../docs/accessibility.md)