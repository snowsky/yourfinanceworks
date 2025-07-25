#!/bin/bash

echo "🧪 Running UI Tests"
echo "=================="

# Install dependencies
npm install

# Run tests with coverage
npm run test:coverage

echo "✅ UI tests completed"
echo "📊 Coverage report: coverage/index.html"