import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import UserLoginPage from "./UserLoginPage";


vi.mock("../api/client", () => ({
  api: { userLogin: vi.fn() },
  applyFormErrors: vi.fn(() => false)
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UserLoginPage", () => {
  it("uses the subscription user login API", async () => {
    api.userLogin.mockResolvedValue({ username: "alice" });
    const onLogin = vi.fn();
    render(
      <ConfigProvider locale={zhCN}>
        <MemoryRouter initialEntries={["/user/login"]}>
          <UserLoginPage onLogin={onLogin} />
        </MemoryRouter>
      </ConfigProvider>
    );

    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "进入订阅门户" }));

    await waitFor(() => expect(api.userLogin).toHaveBeenCalledWith({
      username: "alice",
      password: "secret"
    }));
    expect(onLogin).toHaveBeenCalledWith({ username: "alice" });
    expect(screen.getByText("管理员后台")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "使用管理员账号登录" })).toHaveAttribute("href", "/login");
  });
});
