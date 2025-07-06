#!/bin/bash

# Invoice App Mobile Setup Script
# This script sets up the React Native mobile app for iOS and Android

set -e

echo "🚀 Setting up Invoice App Mobile..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Node.js is installed
check_node() {
    print_status "Checking Node.js installation..."
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js v18 or later."
        exit 1
    fi
    
    NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        print_error "Node.js version 18 or later is required. Current version: $(node -v)"
        exit 1
    fi
    
    print_success "Node.js $(node -v) is installed"
}

# Check if npm is installed
check_npm() {
    print_status "Checking npm installation..."
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed. Please install npm."
        exit 1
    fi
    
    print_success "npm $(npm -v) is installed"
}

# Install Expo CLI globally
install_expo_cli() {
    print_status "Installing Expo CLI..."
    if ! command -v expo &> /dev/null; then
        npm install -g @expo/cli
        print_success "Expo CLI installed"
    else
        print_success "Expo CLI is already installed"
    fi
}

# Install EAS CLI globally
install_eas_cli() {
    print_status "Installing EAS CLI..."
    if ! command -v eas &> /dev/null; then
        npm install -g eas-cli
        print_success "EAS CLI installed"
    else
        print_success "EAS CLI is already installed"
    fi
}

# Install project dependencies
install_dependencies() {
    print_status "Installing project dependencies..."
    npm install
    print_success "Dependencies installed"
}

# Create environment file
create_env_file() {
    print_status "Creating environment configuration..."
    
    if [ ! -f .env ]; then
        cat > .env << EOF
# API Configuration
API_BASE_URL=http://localhost:8000/api

# For production, use your actual API URL
# API_BASE_URL=https://your-production-api.com/api

# Expo Configuration
EXPO_PUBLIC_API_URL=http://localhost:8000/api
EOF
        print_success "Environment file created"
    else
        print_warning "Environment file already exists"
    fi
}

# Check iOS development setup
check_ios_setup() {
    print_status "Checking iOS development setup..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v xcodebuild &> /dev/null; then
            print_success "Xcode is installed"
        else
            print_warning "Xcode is not installed. Install Xcode from the App Store for iOS development."
        fi
        
        if command -v simctl &> /dev/null; then
            print_success "iOS Simulator is available"
        else
            print_warning "iOS Simulator is not available. Install Xcode for iOS development."
        fi
    else
        print_warning "iOS development is only available on macOS"
    fi
}

# Check Android development setup
check_android_setup() {
    print_status "Checking Android development setup..."
    
    if command -v adb &> /dev/null; then
        print_success "Android SDK is installed"
    else
        print_warning "Android SDK is not installed. Install Android Studio for Android development."
    fi
    
    if command -v emulator &> /dev/null; then
        print_success "Android Emulator is available"
    else
        print_warning "Android Emulator is not available. Install Android Studio for Android development."
    fi
}

# Create assets directory and placeholder files
create_assets() {
    print_status "Creating assets directory..."
    
    mkdir -p assets
    
    # Create placeholder icon files if they don't exist
    if [ ! -f assets/icon.png ]; then
        print_warning "assets/icon.png not found. Please add your app icon."
    fi
    
    if [ ! -f assets/splash.png ]; then
        print_warning "assets/splash.png not found. Please add your splash screen."
    fi
    
    if [ ! -f assets/adaptive-icon.png ]; then
        print_warning "assets/adaptive-icon.png not found. Please add your adaptive icon."
    fi
    
    if [ ! -f assets/favicon.png ]; then
        print_warning "assets/favicon.png not found. Please add your favicon."
    fi
}

# Display next steps
show_next_steps() {
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Start the development server:"
    echo "   npm start"
    echo ""
    echo "2. Run on iOS (macOS only):"
    echo "   npm run ios"
    echo ""
    echo "3. Run on Android:"
    echo "   npm run android"
    echo ""
    echo "4. Build for production:"
    echo "   eas build --platform ios"
    echo "   eas build --platform android"
    echo ""
    echo "5. Submit to app stores:"
    echo "   eas submit --platform ios"
    echo "   eas submit --platform android"
    echo ""
    echo "📚 For more information, see the README.md file"
    echo ""
}

# Main setup function
main() {
    echo "Invoice App Mobile Setup"
    echo "========================"
    echo ""
    
    check_node
    check_npm
    install_expo_cli
    install_eas_cli
    install_dependencies
    create_env_file
    check_ios_setup
    check_android_setup
    create_assets
    
    show_next_steps
}

# Run the setup
main "$@" 