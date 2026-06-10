import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup, fireEvent, screen } from "@testing-library/react";
import {
  ThemeProvider,
  THEMES,
  useTheme,
} from "@/components/ui/theme-provider";

function ThemeButtons() {
  const { setTheme } = useTheme();
  return (
    <>
      <button onClick={() => setTheme("premium-dark")}>premium</button>
      <button onClick={() => setTheme("light")}>light</button>
    </>
  );
}

describe("premium-dark theme", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    document.documentElement.className = "";
  });

  it("is registered with a dark base and a scoped class", () => {
    const def = THEMES.find((t) => t.id === "premium-dark");
    expect(def).toBeDefined();
    expect(def?.base).toBe("dark");
    expect(def?.className).toBe("theme-premium-dark");
  });

  it("applies dark + theme-premium-dark classes to <html>", () => {
    render(
      <ThemeProvider defaultTheme="premium-dark" storageKey="test-theme">
        <div />
      </ThemeProvider>
    );
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(
      document.documentElement.classList.contains("theme-premium-dark")
    ).toBe(true);
  });

  it("clears the scoped class when switching back to light", () => {
    render(
      <ThemeProvider defaultTheme="premium-dark" storageKey="test-theme">
        <ThemeButtons />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByText("light"));
    expect(
      document.documentElement.classList.contains("theme-premium-dark")
    ).toBe(false);
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });
});
