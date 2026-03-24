import { useCallback, useEffect, useMemo, useState } from "react";

export interface ColumnDef {
  key: string;
  label: string;
  essential?: boolean;    // Cannot be hidden by user
  defaultVisible?: boolean; // Defaults to true if omitted
}

type ColumnVisibility = Record<string, boolean>;

const STORAGE_PREFIX = "invoice-app-columns-";

function buildDefaults(columns: ColumnDef[]): ColumnVisibility {
  return Object.fromEntries(columns.map((c) => [c.key, c.defaultVisible !== false]));
}

function readVisibility(tableId: string, defaults: ColumnVisibility): ColumnVisibility {
  if (typeof window === "undefined") return defaults;
  try {
    const stored = localStorage.getItem(STORAGE_PREFIX + tableId);
    if (stored) return { ...defaults, ...JSON.parse(stored) };
  } catch {}
  return defaults;
}

export function useColumnVisibility(tableId: string, columns: ColumnDef[]) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const defaults = useMemo(() => buildDefaults(columns), [tableId]);

  const [visibility, setVisibility] = useState<ColumnVisibility>(() =>
    readVisibility(tableId, defaults)
  );

  // Persist on change
  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE_PREFIX + tableId, JSON.stringify(visibility));
  }, [tableId, visibility]);

  // Sync across tabs
  useEffect(() => {
    const sync = () => setVisibility(readVisibility(tableId, defaults));
    if (typeof window === "undefined") return;
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, [tableId, defaults]);

  const isVisible = useCallback(
    (key: string) => visibility[key] !== false,
    [visibility]
  );

  const toggle = useCallback(
    (key: string) => {
      const col = columns.find((c) => c.key === key);
      if (col?.essential) return;
      setVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
    },
    [columns]
  );

  const reset = useCallback(() => {
    setVisibility(defaults);
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_PREFIX + tableId);
    }
  }, [defaults, tableId]);

  const hiddenCount = columns.filter(
    (c) => !c.essential && visibility[c.key] === false
  ).length;

  const visibleCount = columns.filter((c) => visibility[c.key] !== false).length;

  return { isVisible, toggle, reset, hiddenCount, visibleCount, visibility };
}
