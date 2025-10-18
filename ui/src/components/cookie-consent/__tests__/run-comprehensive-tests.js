#!/usr/bin/env node

/**
 * Comprehensive Test Suite Runner for Cookie Consent Banner
 * 
 * This script runs all test suites for the cookie consent banner:
 * - End-to-End Tests
 * - Accessibility Compliance Tests  
 * - GDPR Compliance Tests
 * - Cross-Browser Compatibility Tests
 * - Comprehensive Integration Tests
 */

import { execSync } from 'child_process';
import path from 'path';

const testSuites = [
  {
    name: 'Basic Comprehensive Tests',
    path: 'src/components/cookie-consent/__tests__/comprehensive/BasicTestSuite.test.tsx',
    description: 'Core functionality, GDPR compliance, accessibility, and error handling'
  },
  {
    name: 'End-to-End User Flow Tests',
    path: 'src/components/cookie-consent/__tests__/e2e/CookieConsentE2E.test.tsx',
    description: 'Complete user journeys from first visit to consent management'
  },
  {
    name: 'Accessibility Compliance Tests',
    path: 'src/components/cookie-consent/__tests__/accessibility/AccessibilityCompliance.test.tsx',
    description: 'WCAG compliance, screen reader support, keyboard navigation'
  },
  {
    name: 'GDPR Compliance Tests',
    path: 'src/components/cookie-consent/__tests__/gdpr/GDPRCompliance.test.tsx',
    description: 'Legal compliance, consent management, data subject rights'
  },
  {
    name: 'Cross-Browser Compatibility Tests',
    path: 'src/components/cookie-consent/__tests__/cross-browser/CrossBrowserCompatibility.test.tsx',
    description: 'Browser compatibility, storage fallbacks, feature detection'
  },
  {
    name: 'Comprehensive Integration Tests',
    path: 'src/components/cookie-consent/__tests__/comprehensive/ComprehensiveTestSuite.test.tsx',
    description: 'Integration scenarios, stress testing, real-world usage'
  }
];

const results = {
  passed: [],
  failed: [],
  skipped: []
};

console.log('🍪 Cookie Consent Banner - Comprehensive Test Suite Runner\n');
console.log('Running comprehensive tests to ensure GDPR compliance, accessibility, and cross-browser compatibility.\n');

for (const suite of testSuites) {
  console.log(`\n📋 Running: ${suite.name}`);
  console.log(`📝 Description: ${suite.description}`);
  console.log(`📁 Path: ${suite.path}`);
  console.log('─'.repeat(80));

  try {
    const startTime = Date.now();
    
    // Run the test suite
    execSync(`npm test -- --run ${suite.path}`, {
      stdio: 'inherit',
      cwd: process.cwd()
    });
    
    const duration = Date.now() - startTime;
    console.log(`✅ ${suite.name} - PASSED (${duration}ms)`);
    results.passed.push({ ...suite, duration });
    
  } catch (error) {
    console.log(`❌ ${suite.name} - FAILED`);
    results.failed.push({ ...suite, error: error.message });
    
    // Continue with other tests even if one fails
    console.log('Continuing with remaining test suites...\n');
  }
}

// Print summary
console.log('\n' + '='.repeat(80));
console.log('📊 TEST SUITE SUMMARY');
console.log('='.repeat(80));

console.log(`\n✅ PASSED: ${results.passed.length} test suites`);
results.passed.forEach(suite => {
  console.log(`   • ${suite.name} (${suite.duration}ms)`);
});

if (results.failed.length > 0) {
  console.log(`\n❌ FAILED: ${results.failed.length} test suites`);
  results.failed.forEach(suite => {
    console.log(`   • ${suite.name}`);
  });
}

if (results.skipped.length > 0) {
  console.log(`\n⏭️  SKIPPED: ${results.skipped.length} test suites`);
  results.skipped.forEach(suite => {
    console.log(`   • ${suite.name}`);
  });
}

const totalDuration = results.passed.reduce((sum, suite) => sum + suite.duration, 0);
console.log(`\n⏱️  Total Duration: ${totalDuration}ms`);

// Coverage areas summary
console.log('\n📋 COVERAGE AREAS TESTED:');
console.log('   • End-to-End User Flows');
console.log('   • GDPR Legal Compliance');
console.log('   • WCAG Accessibility Standards');
console.log('   • Cross-Browser Compatibility');
console.log('   • Error Handling & Recovery');
console.log('   • Performance & Memory Management');
console.log('   • Analytics Integration');
console.log('   • Theme & Customization');
console.log('   • Real-World Usage Scenarios');

// Requirements coverage
console.log('\n📋 REQUIREMENTS COVERAGE:');
console.log('   • Requirement 4.1: ARIA attributes and screen reader support');
console.log('   • Requirement 5.1: No non-essential cookies before consent');
console.log('   • Requirement 5.2: Essential cookies only by default');
console.log('   • Requirement 5.3: Clear cookie category information');
console.log('   • Requirement 5.4: Consent withdrawal capability');

// Exit with appropriate code
if (results.failed.length > 0) {
  console.log('\n❌ Some test suites failed. Please review the output above.');
  process.exit(1);
} else {
  console.log('\n✅ All test suites passed successfully!');
  console.log('🎉 Cookie Consent Banner is ready for production use.');
  process.exit(0);
}