import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "yfw-appearance";
const EVENT_NAME = "appearance-settings-changed";

export interface AppearanceSettings {
  showClock: boolean;
  showDate: boolean;
  showLocalClock: boolean;
  showUTCClock: boolean;
}

const defaults: AppearanceSettings = {
  showClock: true,
  showDate: true,
  showLocalClock: true,
  showUTCClock: false,
};

function readSettings(): AppearanceSettings {
  if (typeof window === "undefined") return defaults;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return defaults;
    return { ...defaults, ...JSON.parse(stored) };
  } catch {
    return defaults;
  }
}

export function useAppearanceSettings() {
  const [settings, setSettings] = useState<AppearanceSettings>(readSettings);

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: settings }));
    }
  }, [settings]);

  useEffect(() => {
    const sync = () => {
      setSettings(prev => {
        const next = readSettings();
        // Return same reference if nothing changed so this effect doesn't re-fire
        if (prev.showClock === next.showClock && prev.showDate === next.showDate && prev.showLocalClock === next.showLocalClock && prev.showUTCClock === next.showUTCClock) {
          return prev;
        }
        return next;
      });
    };
    if (typeof window === "undefined") return;
    window.addEventListener("storage", sync);
    window.addEventListener(EVENT_NAME, sync as EventListener);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(EVENT_NAME, sync as EventListener);
    };
  }, []);

  const update = useCallback((partial: Partial<AppearanceSettings>) => {
    setSettings(prev => ({ ...prev, ...partial }));
  }, []);

  return { settings, update };
}
