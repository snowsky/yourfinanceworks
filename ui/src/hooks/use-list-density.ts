import { useCallback, useEffect, useState } from "react";

export type ListDensity = "comfortable" | "compact";

const STORAGE_KEY = "invoice-app-list-density";
const EVENT_NAME = "list-density-changed";

function normalizeDensity(value: string | null): ListDensity {
  return value === "compact" ? "compact" : "comfortable";
}

function readDensity(): ListDensity {
  if (typeof window === "undefined") return "comfortable";
  return normalizeDensity(localStorage.getItem(STORAGE_KEY));
}

function applyDensityToDocument(density: ListDensity) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-list-density", density);
}

export function useListDensity() {
  const [density, setDensity] = useState<ListDensity>(readDensity);

  useEffect(() => {
    applyDensityToDocument(density);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, density);
      window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: density }));
    }
  }, [density]);

  useEffect(() => {
    const syncDensity = () => setDensity(readDensity());
    if (typeof window === "undefined") return;

    window.addEventListener("storage", syncDensity);
    window.addEventListener(EVENT_NAME, syncDensity as EventListener);
    return () => {
      window.removeEventListener("storage", syncDensity);
      window.removeEventListener(EVENT_NAME, syncDensity as EventListener);
    };
  }, []);

  const toggleDensity = useCallback(() => {
    setDensity((current) => (current === "comfortable" ? "compact" : "comfortable"));
  }, []);

  return { density, setDensity, toggleDensity };
}

