// Simple test to check if inventory information is displayed in the UI
// This can be run in the browser console when viewing an invoice

console.log("🔍 Testing UI Inventory Display");

// Check if we're on an invoice page
const currentUrl = window.location.href;
if (!currentUrl.includes('/invoices/')) {
  console.log("❌ Not on an invoice page. Please navigate to an invoice edit page first.");
} else {
  console.log("✅ On invoice page:", currentUrl);
  
  // Look for inventory information elements
  const inventoryElements = document.querySelectorAll('[class*="inventory"], [title*="inventory"], [title*="Inventory"]');
  console.log(`🔍 Found ${inventoryElements.length} potential inventory elements:`, inventoryElements);
  
  // Look for Package icons (inventory indicators)
  const packageIcons = document.querySelectorAll('svg[class*="lucide-package"], [class*="Package"]');
  console.log(`🔍 Found ${packageIcons.length} package icons:`, packageIcons);
  
  // Look for inventory information sections
  const inventoryInfoSections = Array.from(document.querySelectorAll('*')).filter(el => 
    el.textContent && el.textContent.includes('Inventory Information')
  );
  console.log(`🔍 Found ${inventoryInfoSections.length} inventory information sections:`, inventoryInfoSections);
  
  // Look for SKU, stock, or other inventory-related text
  const inventoryText = Array.from(document.querySelectorAll('*')).filter(el => 
    el.textContent && (
      el.textContent.includes('SKU:') || 
      el.textContent.includes('Current Stock:') ||
      el.textContent.includes('Unit Price:') ||
      el.textContent.includes('avail')
    )
  );
  console.log(`🔍 Found ${inventoryText.length} elements with inventory text:`, inventoryText);
  
  // Check form data in React DevTools (if available)
  if (window.React && window.React.version) {
    console.log("✅ React detected, version:", window.React.version);
    
    // Try to find React components with inventory data
    const reactElements = document.querySelectorAll('[data-reactroot], [id="root"]');
    if (reactElements.length > 0) {
      console.log("✅ Found React root elements:", reactElements.length);
    }
  }
  
  // Summary
  const hasInventoryDisplay = inventoryInfoSections.length > 0 || inventoryText.length > 0;
  
  if (hasInventoryDisplay) {
    console.log("🎉 SUCCESS: Inventory information appears to be displayed in the UI!");
  } else {
    console.log("❌ ISSUE: No inventory information found in the UI. Check:");
    console.log("1. Are you editing an invoice that has inventory items?");
    console.log("2. Has the invoice been created from inventory items?");
    console.log("3. Are there any console errors?");
  }
}

// Instructions
console.log("\n📋 Instructions:");
console.log("1. Navigate to an invoice that was created from inventory items");
console.log("2. Click 'Edit' on the invoice");
console.log("3. Look for inventory information sections");
console.log("4. Check the browser console for any errors");