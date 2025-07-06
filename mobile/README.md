# Invoice App Mobile

A React Native mobile application that adapts the web UI components from the main invoice management system.

## Overview

This mobile app takes the existing web UI components from the `ui/` folder and adapts them for mobile use with React Native. The app provides a native mobile experience while maintaining the same design language and functionality as the web version.

## Web UI Adaptation

### How We Adapted the Web Components

The mobile app successfully adapts the web UI components by:

1. **Component Structure**: Each web component has been recreated as a React Native component with equivalent functionality
2. **Design Language**: Maintains the same visual design, colors, and layout patterns
3. **User Experience**: Preserves the same user flows and interactions
4. **Data Models**: Uses the same data structures and API endpoints

### Adapted Screens

#### 1. Login Screen (`LoginScreen.tsx`)
**Web Source**: `ui/src/pages/Login.tsx`

**Adaptations**:
- Converted HTML form to React Native `TextInput` components
- Replaced CSS classes with StyleSheet objects
- Added mobile-specific features like keyboard handling
- Maintained the same visual design with cards and buttons
- Preserved Google SSO button (placeholder for future implementation)

**Key Features**:
- Email and password input with validation
- Show/hide password toggle
- Loading states with activity indicators
- Error handling and display
- Navigation to signup screen

#### 2. Signup Screen (`SignupScreen.tsx`)
**Web Source**: `ui/src/pages/Signup.tsx`

**Adaptations**:
- Converted HTML form to React Native `TextInput` components
- Replaced CSS classes with StyleSheet objects
- Added comprehensive form validation
- Maintained the same visual design with cards and buttons
- Preserved Google SSO button (placeholder for future implementation)

**Key Features**:
- Complete registration form with all required fields
- Organization name, first name, last name, email, password, confirm password
- Real-time form validation with error messages
- Password strength validation (minimum 6 characters)
- Password confirmation matching
- Email format validation
- Show/hide password toggles for both password fields
- Loading states with activity indicators
- Navigation back to login screen

#### 3. Dashboard Screen (`DashboardScreen.tsx`)
**Web Source**: `ui/src/pages/Index.tsx`

**Adaptations**:
- Converted grid layout to mobile-friendly card layout
- Replaced chart components with simplified stat cards
- Added quick action buttons for navigation
- Maintained the same color scheme and typography
- Added pull-to-refresh functionality

**Key Features**:
- Financial overview cards (Total Income, Pending Amount, etc.)
- Quick action buttons for main features
- Recent activity list
- Loading states and error handling
- Responsive design for different screen sizes

#### 4. Invoices Screen (`InvoicesScreen.tsx`)
**Web Source**: `ui/src/pages/Invoices.tsx`

**Adaptations**:
- Converted table layout to card-based list
- Replaced search and filter UI with mobile-optimized components
- Maintained the same data structure and status handling
- Added mobile navigation patterns

**Key Features**:
- Invoice list with detailed cards
- Search functionality
- Status filtering with modal picker (All Statuses, Paid, Pending, Overdue, Draft)
- Pull-to-refresh
- Navigation to edit/create invoices

#### 5. New Invoice Screen (`NewInvoiceScreen.tsx`)
**Web Source**: `ui/src/pages/NewInvoice.tsx` and `ui/src/components/invoices/InvoiceForm.tsx`

**Adaptations**:
- Converted complex web form to mobile-optimized interface
- Replaced date pickers with mobile-friendly selectors
- Maintained all form validation and business logic
- Added real-time calculations and summary

**Key Features**:
- Complete invoice creation form
- Client selection with modal picker
- Invoice details (number, dates, currency, status)
- Dynamic invoice items with add/remove functionality
- Real-time calculations (subtotal, total, outstanding)
- Payment amount tracking
- Form validation with error messages
- Invoice summary with financial breakdown
- Mobile-optimized keyboard handling

## Architecture

### Screen Management
The app uses a simple state-based navigation system in `App.tsx`:

```typescript
type Screen = 'login' | 'signup' | 'dashboard' | 'invoices' | 'newInvoice' | 'clients' | 'payments' | 'settings';
```

### Component Structure
```
src/
├── screens/
│   ├── LoginScreen.tsx      # Adapted from web Login.tsx
│   ├── SignupScreen.tsx     # Adapted from web Signup.tsx
│   ├── DashboardScreen.tsx  # Adapted from web Index.tsx
│   ├── InvoicesScreen.tsx   # Adapted from web Invoices.tsx
│   └── NewInvoiceScreen.tsx # Adapted from web NewInvoice.tsx + InvoiceForm.tsx
```

### Data Flow
- Mock data is used for demonstration (replace with actual API calls)
- Same data models as web version
- Consistent error handling patterns
- **State Management**: Invoices are managed at the App level and passed down to screens
- **Real-time Updates**: New invoices are immediately added to the list after creation

## Key Differences from Web Version

### 1. Navigation
- **Web**: React Router with URL-based navigation
- **Mobile**: State-based navigation with screen transitions

### 2. Layout
- **Web**: CSS Grid and Flexbox with responsive breakpoints
- **Mobile**: Flexbox-based layouts optimized for mobile screens

### 3. Interactions
- **Web**: Mouse and keyboard interactions
- **Mobile**: Touch gestures, pull-to-refresh, mobile-optimized buttons

### 4. Components
- **Web**: HTML elements with CSS classes
- **Mobile**: React Native components with StyleSheet objects

## Setup and Installation

### Prerequisites
- Node.js (v18 or higher)
- npm or yarn
- Expo CLI
- iOS Simulator (for iOS) or Android Emulator (for Android)

### Installation Steps

1. **Install Dependencies**:
   ```bash
   cd mobile
   npm install
   ```

2. **Start the Development Server**:
   ```bash
   npm start
   ```

3. **Run on Simulator/Device**:
   - Press `i` for iOS Simulator
   - Press `a` for Android Emulator
   - Scan QR code with Expo Go app on your device

### Troubleshooting

#### Common Issues:

1. **Metro Bundler Errors**:
   ```bash
   npx expo start --clear
   ```

2. **iOS Simulator Issues**:
   ```bash
   npx expo run:ios
   ```

3. **Android Emulator Issues**:
   ```bash
   npx expo run:android
   ```

## Development Guidelines

### Adding New Screens

1. **Create the Screen Component**:
   ```typescript
   // src/screens/NewScreen.tsx
   import React from 'react';
   import { View, Text, StyleSheet } from 'react-native';
   
   interface NewScreenProps {
     // Define props
   }
   
   const NewScreen: React.FC<NewScreenProps> = ({ /* props */ }) => {
     return (
       <View style={styles.container}>
         <Text>New Screen</Text>
       </View>
     );
   };
   
   const styles = StyleSheet.create({
     container: {
       flex: 1,
       backgroundColor: '#f5f5f5',
     },
   });
   
   export default NewScreen;
   ```

2. **Add to App.tsx**:
   ```typescript
   // Add screen type
   type Screen = 'login' | 'dashboard' | 'invoices' | 'newScreen';
   
   // Add navigation handler
   const handleNavigateToNewScreen = () => {
     setCurrentScreen('newScreen');
   };
   
   // Add to renderScreen function
   case 'newScreen':
     return <NewScreen /* props */ />;
   ```

### Styling Guidelines

1. **Use StyleSheet.create()** for all styles
2. **Follow the color scheme** from the web version:
   - Primary: `#007AFF`
   - Success: `#10B981`
   - Warning: `#F59E0B`
   - Error: `#EF4444`
   - Gray: `#6B7280`

3. **Maintain consistency** with web component spacing and typography

### API Integration

To integrate with the actual backend:

1. **Replace mock data** with API calls
2. **Add authentication** with token storage
3. **Implement error handling** for network requests
4. **Add loading states** for async operations

Example API integration:
```typescript
// services/api.ts
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
});

export const invoiceApi = {
  getInvoices: async () => {
    const response = await api.get('/invoices');
    return response.data;
  },
  // Add more API methods
};
```

## Future Enhancements

### Planned Features
1. **Complete Navigation**: Implement React Navigation for better screen management
2. **Authentication**: Full integration with backend auth system
3. **Offline Support**: Cache data for offline usage
4. **Push Notifications**: Invoice reminders and updates
5. **Camera Integration**: Scan receipts and documents
6. **PDF Generation**: Generate and view invoices on mobile

### Additional Screens to Adapt
- Client management screen
- Payment tracking screen
- Settings screen
- Invoice creation/editing forms
- User profile screen

## Contributing

When contributing to the mobile app:

1. **Follow the adaptation pattern** established by existing screens
2. **Maintain design consistency** with the web version
3. **Test on both iOS and Android** simulators
4. **Update this README** when adding new features
5. **Use TypeScript** for all new components

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the web UI source code for reference
3. Ensure all dependencies are properly installed
4. Clear Metro cache if experiencing build issues

---

The mobile app successfully demonstrates how to adapt web UI components to React Native while maintaining the same user experience and design language. 