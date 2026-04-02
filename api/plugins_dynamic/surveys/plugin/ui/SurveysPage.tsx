/**
 * Plugin-specific wrapper for the shared SurveysPage.
 * This file handles main-app hook integration.
 */

import React from "react";
import SharedSurveysPage from "../../shared/ui/pages/SurveysPage";
import { useOrganizations } from "@/hooks/useOrganizations";

export default function SurveysPage() {
  const { data: organizations, isLoading: isLoadingOrganizations } = useOrganizations();

  return (
    <SharedSurveysPage 
      organizations={organizations} 
      isLoadingOrganizations={isLoadingOrganizations} 
    />
  );
}
