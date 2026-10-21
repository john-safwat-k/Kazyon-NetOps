import React, { createContext, useContext, useEffect, useState } from "react";
import { ThemeMode } from "./tokens";

const THEME_STORAGE_KEY = "kz_netops_theme";

interface ThemeContextValue {
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "light",
  setTheme: () => undefined,
  toggleTheme: () => undefined,
});

export function ThemeProvider({
  defaultTheme = "light",
  children,
}: {
  defaultTheme?: ThemeMode;
  children: React.ReactNode;
}) {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    if (typeof window !== "undefined") {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === "light" || saved === "dark") {
        return saved;
      }
    }
    return defaultTheme;
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Ignore storage write errors in private contexts
    }
  }, [theme]);

  const setTheme = (next: ThemeMode) => setThemeState(next);
  const toggleTheme = () => setThemeState((prev) => (prev === "dark" ? "light" : "dark"));

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
