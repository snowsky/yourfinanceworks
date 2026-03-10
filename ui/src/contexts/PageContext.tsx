import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';

export type PageEntity = {
  type: string;
  id?: number;
  name?: string;
};

export type PageContextState = {
  pathname: string;
  search?: string;
  hash?: string;
  title?: string;
  entity?: PageEntity;
  metadata?: Record<string, unknown>;
};

type PageContextValue = {
  pageContext: PageContextState;
  setPageContext: (updates: Partial<PageContextState>) => void;
  clearPageContext: () => void;
};

const PageContext = createContext<PageContextValue | undefined>(undefined);

export const PageContextProvider = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const [pageContext, setPageContextState] = useState<PageContextState>({
    pathname: location.pathname,
    search: location.search,
    hash: location.hash
  });

  useEffect(() => {
    // Reset contextual entity metadata on navigation to avoid stale context
    setPageContextState({
      pathname: location.pathname,
      search: location.search,
      hash: location.hash
    });
  }, [location.pathname, location.search, location.hash]);

  const setPageContext = useCallback((updates: Partial<PageContextState>) => {
    setPageContextState((prev) => ({
      ...prev,
      ...updates
    }));
  }, []);

  const clearPageContext = useCallback(() => {
    setPageContextState({
      pathname: location.pathname,
      search: location.search,
      hash: location.hash
    });
  }, [location.pathname, location.search, location.hash]);

  const value = useMemo(() => ({ pageContext, setPageContext, clearPageContext }), [pageContext, setPageContext, clearPageContext]);

  return (
    <PageContext.Provider value={value}>
      {children}
    </PageContext.Provider>
  );
};

export const usePageContext = () => {
  const context = useContext(PageContext);
  if (!context) {
    throw new Error('usePageContext must be used within a PageContextProvider');
  }
  return context;
};
