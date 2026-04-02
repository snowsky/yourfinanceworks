import React, { Suspense } from 'react';
import { PluginErrorBoundary } from '@/components/plugins/PluginErrorBoundary';

const TimeTrackingInternal = React.lazy(() => import('./TimeTrackingInternal'));

/**
 * TimeTracking — wrapper that providing isolation for the time_tracking plugin.
 */
export default function TimeTracking() {
  return (
    <PluginErrorBoundary name="Time Tracking" className="m-8">
      <Suspense 
        fallback={
          <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <p className="text-muted-foreground animate-pulse font-medium">Loading time tracking logs…</p>
          </div>
        }
      >
        <TimeTrackingInternal />
      </Suspense>
    </PluginErrorBoundary>
  );
}
