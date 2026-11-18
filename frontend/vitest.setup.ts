import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom lacks a few browser APIs used by framer-motion / gsap.
window.matchMedia =
  window.matchMedia ||
  ((query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList);

Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {});
globalThis.ResizeObserver =
  globalThis.ResizeObserver ||
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };

// framer-motion `whileInView` needs an IntersectionObserver in jsdom.
globalThis.IntersectionObserver =
  globalThis.IntersectionObserver ||
  (class {
    root = null;
    rootMargin = "";
    thresholds = [];
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
  } as unknown as typeof IntersectionObserver);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
