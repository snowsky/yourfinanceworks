# UI: Local Export Destination Support

## Changes Made

### 1. Updated ExportDestination Interface
**File:** `ui/src/lib/api.ts`

Added support for 'local' destination type and testable field:
```typescript
export interface ExportDestination {
  // ... existing fields ...
  destination_type: 's3' | 'azure' | 'gcs' | 'google_drive' | 'local';
  testable?: boolean;
}

export interface ExportDestinationCreate {
  // ... existing fields ...
  destination_type: 's3' | 'azure' | 'gcs' | 'google_drive' | 'local';
}
```

### 2. Updated ExportDestinationsTab Component
**File:** `ui/src/components/settings/ExportDestinationsTab.tsx`

#### Added Local Type Label
```typescript
const getDestinationTypeLabel = (type: string) => {
  switch (type) {
    case 's3': return 'AWS S3';
    case 'azure': return 'Azure Blob Storage';
    case 'gcs': return 'Google Cloud Storage';
    case 'google_drive': return 'Google Drive';
    case 'local': return 'Local File System';
    default: return type;
  }
};
```

#### Conditional Test Button Rendering
```typescript
{destination.testable && (
  <Button
    variant="outline"
    size="sm"
    onClick={() => handleTestConnection(destination.id)}
    disabled={testingId === destination.id}
  >
    {testingId === destination.id ? (
      <Loader2 className="h-4 w-4 animate-spin" />
    ) : (
      t('settings.test')
    )}
  </Button>
)}
```

#### Added Local Option to Destination Type Selector
```typescript
<SelectContent>
  <SelectItem value="s3">AWS S3</SelectItem>
  <SelectItem value="azure">Azure Blob Storage</SelectItem>
  <SelectItem value="gcs">Google Cloud Storage</SelectItem>
  <SelectItem value="google_drive">Google Drive</SelectItem>
  <SelectItem value="local">Local File System</SelectItem>
</SelectContent>
```

## Behavior

### Test Button Visibility
- **Cloud Providers (S3, Azure, GCS, Google Drive):** Test button is visible and enabled
- **Local File System:** Test button is hidden (testable=false)

### Destination Type Display
- Local destinations show as "Local File System" in the UI
- All destination types are selectable when creating new destinations

## Backend Integration
The `testable` field is provided by the backend API:
- Cloud providers: `testable: true`
- Local destinations: `testable: false`

The UI uses this field to conditionally render the test button, providing a better user experience by not showing unnecessary test functionality for local destinations.
