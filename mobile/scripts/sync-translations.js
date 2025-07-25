#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const sourceDir = path.join(__dirname, '../../ui/src/i18n/locales');
const targetDir = path.join(__dirname, '../src/i18n/locales');

// Ensure target directory exists
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

// Copy all JSON files
const files = fs.readdirSync(sourceDir).filter(file => file.endsWith('.json'));

files.forEach(file => {
  const sourcePath = path.join(sourceDir, file);
  const targetPath = path.join(targetDir, file);
  
  fs.copyFileSync(sourcePath, targetPath);
  console.log(`Synced: ${file}`);
});

console.log(`✅ Synced ${files.length} translation files`);