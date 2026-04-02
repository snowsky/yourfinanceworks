import React, { Suspense } from 'react';
import { PluginErrorBoundary } from '@/components/plugins/PluginErrorBoundary';

const ProjectDetailInternal = React.lazy(() => import('./ProjectDetailInternal'));

/**
 * ProjectDetail — wrapper that providing isolation for the time_tracking plugin.
 */
export default function ProjectDetail() {
  return (
    <PluginErrorBoundary name="Projects" className="m-8">
      <Suspense 
        fallback={
          <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <p className="text-muted-foreground animate-pulse font-medium">Loading project details…</p>
          </div>
        }
      >
        <ProjectDetailInternal />
      </Suspense>
    </PluginErrorBoundary>
  );
}
