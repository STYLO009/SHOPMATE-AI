import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LoginPage from "@/app/login/page";
import { ApiRequestError } from "@/lib/api";

const push = vi.fn();
const login = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/login",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    error: null,
    refresh: vi.fn(),
    login,
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    auth: {
      ...actual.auth,
      forgotPassword: vi.fn().mockResolvedValue({ message: "ok" }),
      googleLoginUrl: () => "http://localhost:8000/api/auth/google/login",
    },
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    push.mockClear();
    login.mockReset();
  });

  it("renders the sign-in form", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("login-form")).toBeInTheDocument();
    expect(screen.getByTestId("login-submit")).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("submits credentials and redirects to the dashboard", async () => {
    login.mockResolvedValue({ id: "u1", email: "a@example.com" });
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "a@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "Passw0rd123" },
    });
    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() =>
      expect(login).toHaveBeenCalledWith("a@example.com", "Passw0rd123"),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
  });

  it("surfaces backend auth errors without redirecting", async () => {
    login.mockRejectedValue(
      new ApiRequestError(401, "invalid_credentials", "Invalid email or password."),
    );
    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: "a@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByTestId("login-submit"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password.",
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("links to the Google backend OAuth redirect", () => {
    render(<LoginPage />);
    expect(screen.getByTestId("google-login")).toHaveAttribute(
      "href",
      "http://localhost:8000/api/auth/google/login",
    );
  });
});
