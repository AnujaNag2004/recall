import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "./login-form";
import { ForgotPasswordForm, ResetPasswordForm } from "./password-forms";
import { SignupForm } from "./signup-form";

const auth = {
  signInWithPassword: vi.fn(),
  signInWithOAuth: vi.fn(),
  signUp: vi.fn(),
  resetPasswordForEmail: vi.fn(),
  updateUser: vi.fn(),
};
const router = { replace: vi.fn(), refresh: vi.fn() };
let params = new URLSearchParams();

vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({ auth }) }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => params,
}));

async function fillLogin() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), "priya@example.com");
  await user.type(screen.getByLabelText("Password"), "correct-horse");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

beforeEach(() => {
  vi.clearAllMocks();
  params = new URLSearchParams();
});

describe("LoginForm", () => {
  it("signs in and goes to the app", async () => {
    auth.signInWithPassword.mockResolvedValue({ error: null });
    render(<LoginForm />);
    await fillLogin();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/home"));
    expect(auth.signInWithPassword).toHaveBeenCalledWith({
      email: "priya@example.com",
      password: "correct-horse",
    });
  });

  it("returns to the page they were heading for", async () => {
    params = new URLSearchParams("next=/library");
    auth.signInWithPassword.mockResolvedValue({ error: null });
    render(<LoginForm />);
    await fillLogin();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/library"));
  });

  it("ignores a next parameter pointing at another site", async () => {
    params = new URLSearchParams("next=https://evil.example");
    auth.signInWithPassword.mockResolvedValue({ error: null });
    render(<LoginForm />);
    await fillLogin();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/home"));
  });

  it("gives the same message for a wrong password and an unknown email", async () => {
    auth.signInWithPassword.mockResolvedValue({ error: { code: "invalid_credentials" } });
    render(<LoginForm />);
    await fillLogin();
    expect(await screen.findByRole("alert")).toHaveTextContent("don't match");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("explains an expired email link", () => {
    params = new URLSearchParams("error=link");
    render(<LoginForm />);
    expect(screen.getByRole("alert")).toHaveTextContent("expired");
  });
});

describe("SignupForm", () => {
  async function fillSignup() {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Name"), "Priya S");
    await user.type(screen.getByLabelText("Email"), "priya@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));
  }

  it("sends the name along and asks them to confirm their email", async () => {
    auth.signUp.mockResolvedValue({ data: { session: null }, error: null });
    render(<SignupForm />);
    await fillSignup();
    expect(await screen.findByRole("status")).toHaveTextContent("priya@example.com");
    expect(auth.signUp.mock.calls[0][0].options.data).toEqual({ full_name: "Priya S" });
  });

  it("goes straight to the app when no confirmation is needed", async () => {
    auth.signUp.mockResolvedValue({ data: { session: { access_token: "t" } }, error: null });
    render(<SignupForm />);
    await fillSignup();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/home"));
  });

  it("explains a rejected password", async () => {
    auth.signUp.mockResolvedValue({ data: {}, error: { code: "weak_password" } });
    render(<SignupForm />);
    await fillSignup();
    expect(await screen.findByRole("alert")).toHaveTextContent("stronger password");
  });
});

describe("password reset", () => {
  it("says the same thing whether or not the email exists", async () => {
    auth.resetPasswordForEmail.mockResolvedValue({ error: { code: "user_not_found" } });
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);
    await user.type(screen.getByLabelText("Email"), "nobody@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If that email has an account");
  });

  it("saves a new password and enters the app", async () => {
    auth.updateUser.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    render(<ResetPasswordForm />);
    await user.type(screen.getByLabelText("New password"), "a-new-password");
    await user.click(screen.getByRole("button", { name: "Save password" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/home"));
  });
});
