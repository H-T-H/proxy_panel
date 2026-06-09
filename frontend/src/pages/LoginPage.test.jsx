import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { message } from "antd";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import LoginPage from "./LoginPage";


vi.mock("../api/client", () => ({
  api: { login: vi.fn() },
  applyFormErrors: vi.fn(() => false)
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("LoginPage", () => {
  it("submits credentials and returns the logged-in user", async () => {
    const onLogin = vi.fn();
    api.login.mockResolvedValueOnce({ username: "admin" });
    render(<LoginPage onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /登\s*录/ }));

    await waitFor(() => expect(api.login).toHaveBeenCalledWith({ username: "admin", password: "secret" }));
    expect(onLogin).toHaveBeenCalledWith({ username: "admin" });
  });

  it("shows permission errors", async () => {
    const error = vi.spyOn(message, "error").mockImplementation(() => {});
    api.login.mockRejectedValueOnce(new Error("该账号没有后台管理权限"));
    render(<LoginPage onLogin={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "member" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: /登\s*录/ }));

    await waitFor(() => expect(error).toHaveBeenCalledWith("该账号没有后台管理权限"));
  });
});
