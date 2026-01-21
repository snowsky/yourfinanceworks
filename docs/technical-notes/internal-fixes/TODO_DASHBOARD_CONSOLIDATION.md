# TODO: Dashboard Consolidation

## Date: 2024
## Status: PENDING DECISION

## Context

User requested to use `ProfessionalDashboard.tsx` (web) in the mobile app and remove `DashboardScreen.tsx`.

## Problem

**ProfessionalDashboard.tsx** and **DashboardScreen.tsx** are fundamentally incompatible:

- **ProfessionalDashboard.tsx** (`ui/src/components/dashboard/ProfessionalDashboard.tsx`)
  - React web component
  - Uses React Router, browser DOM APIs
  - Uses ShadCN UI components (web-only)
  - Tailwind CSS styling

- **DashboardScreen.tsx** (`mobile/src/screens/DashboardScreen.tsx`)
  - React Native component
  - Uses React Native components (View, ScrollView, TouchableOpacity)
  - Uses Expo and native mobile APIs
  - StyleSheet styling
  - Currently used in `mobile/App.tsx` (line 8, line 390)

## Options

### Option 1: Keep Both Dashboards (RECOMMENDED)
- **Pros**: Each platform has optimized UX, no breaking changes
- **Cons**: Code duplication
- **Effort**: None (current state)

### Option 2: Extract Shared Logic
- **Pros**: Reuse business logic, maintain separate UIs
- **Cons**: Requires refactoring
- **Effort**: Medium
- **Tasks**:
  - Create shared hooks for dashboard data fetching
  - Create shared utilities for currency formatting
  - Create shared types/interfaces
  - Keep UI components separate

### Option 3: React Native Web Migration
- **Pros**: True code sharing between platforms
- **Cons**: Major architectural change, potential performance issues
- **Effort**: High
- **Tasks**:
  - Rewrite entire mobile app to use React Native Web
  - Migrate all screens and components
  - Test on all platforms
  - Handle platform-specific differences

## Recommendation

**Keep both dashboards** as they serve different platforms with different UX requirements. Mobile and web have fundamentally different interaction patterns.

If code reuse is desired, implement **Option 2** to extract shared business logic while maintaining platform-specific UIs.

## Next Steps

1. Decide on approach (Option 1, 2, or 3)
2. If Option 2: Create shared logic layer
   - Extract dashboard data fetching logic
   - Create shared currency formatting utilities
   - Create shared TypeScript interfaces
3. Document decision in project README

## Files Involved

- `mobile/src/screens/DashboardScreen.tsx` - Mobile dashboard (React Native)
- `ui/src/components/dashboard/ProfessionalDashboard.tsx` - Web dashboard (React)
- `mobile/App.tsx` - Mobile app entry point (uses DashboardScreen)

## Related Issues

None currently tracked.
