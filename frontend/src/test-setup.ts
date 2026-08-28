import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement window.matchMedia -- polyfill it so components that check
// prefers-color-scheme (useTheme) don't crash in tests.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
