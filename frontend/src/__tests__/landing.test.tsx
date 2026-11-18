import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LandingPage from "@/app/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    error: null,
    refresh: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("LandingPage", () => {
  it("renders the hero and primary CTAs", () => {
    render(<LandingPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /shop smarter/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start researching/i })).toHaveAttribute(
      "href",
      "/signup",
    );
    // Hero + navbar both link to /login.
    for (const link of screen.getAllByRole("link", { name: /^sign in$/i })) {
      expect(link).toHaveAttribute("href", "/login");
    }
  });

  it("documents the agent pipeline steps", () => {
    render(<LandingPage />);
    for (const step of ["Understand", "Route", "Search", "Rank", "Advise"]) {
      expect(screen.getByText(step)).toBeInTheDocument();
    }
  });

  it("states the sample-data honesty policy", () => {
    render(<LandingPage />);
    expect(screen.getByText(/sample dataset/i)).toBeInTheDocument();
  });
});
