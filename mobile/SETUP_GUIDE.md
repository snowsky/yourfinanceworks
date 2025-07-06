# Mobile App Setup Guide

## Quick Start

This is a minimal working version of the Invoice App mobile application. Follow these steps to get it running:

### 1. Prerequisites

Make sure you have the following installed:
- **Node.js** (v18 or later)
- **npm** or **yarn**
- **Expo CLI** (`npm install -g @expo/cli`)

### 2. Install Dependencies

```bash
cd mobile
npm install
```

### 3. Start the Development Server

```bash
npm start
```

### 4. Run on Device/Simulator

- **iOS Simulator** (macOS only): Press `i` in the terminal or run `npm run ios`
- **Android Emulator**: Press `a` in the terminal or run `npm run android`
- **Physical Device**: Scan the QR code with the Expo Go app

## What's Included

This minimal version includes:
- ✅ Basic Expo setup with TypeScript
- ✅ Simple welcome screen
- ✅ Clean, modern UI design
- ✅ Ready for development

## Next Steps

Once this basic version is working, you can gradually add more features:

1. **Add Navigation**: Install React Navigation for multi-screen support
2. **Add API Integration**: Install Axios for backend communication
3. **Add State Management**: Install React Query for data fetching
4. **Add Authentication**: Implement login/signup screens
5. **Add Core Features**: Dashboard, invoices, clients, payments

## Troubleshooting

### Common Issues

1. **Node.js not found**: Make sure Node.js is installed and in your PATH
2. **Expo CLI not found**: Install with `npm install -g @expo/cli`
3. **Port already in use**: Kill the process using the port or use a different port

### Getting Help

- Check the [Expo documentation](https://docs.expo.dev/)
- Review the [React Native documentation](https://reactnative.dev/)
- Open an issue on GitHub if you encounter problems

## Current Status

This is a **minimal working version** that demonstrates the basic setup. The full-featured version with all screens and functionality is available in the `src/` directory but requires additional dependencies to be installed gradually.

---

**Note**: This setup prioritizes getting a working app quickly. You can add more features incrementally as needed. 