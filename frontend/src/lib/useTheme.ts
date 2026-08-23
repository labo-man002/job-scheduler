import { useLayoutEffect, useState } from "react";

type Theme = "light" | "dark";
const STORAGE_KEY = "theme";

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    // Storage/matchMedia access can throw (e.g. an iframe with storage access
    // blocked) -- fall back rather than crashing the whole app on first render.
    return "light";
  }
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  // useLayoutEffect (not useEffect) so the .dark class lands before the browser's
  // first paint -- otherwise a dark-mode user sees a flash of the light theme on
  // every load, since useEffect only runs after paint.
  useLayoutEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Theme still works for this session; it just won't persist across reloads.
    }
  }, [theme]);

  return { theme, toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")) };
}
