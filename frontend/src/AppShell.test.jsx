import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./api/client";
import { Shell } from "./main";


vi.mock("./api/client", () => ({
  api: {
    me: vi.fn(),
    logout: vi.fn(),
    userMe: vi.fn()
  }
}));

vi.mock("./pages/DashboardPage", () => ({ default: () => <div>仪表盘内容</div> }));
vi.mock("./pages/ClientsPage", () => ({ default: () => <div>客户端页</div> }));
vi.mock("./pages/LoginPage", () => ({ default: () => <div>登录页</div> }));
vi.mock("./pages/NodesPage", () => ({ default: () => <div>节点页</div> }));
vi.mock("./pages/SettingsPage", () => ({ default: () => <div>设置页</div> }));
vi.mock("./pages/SourcesPage", () => ({ default: () => <div>订阅源页</div> }));
vi.mock("./pages/UsersPage", () => ({ default: () => <div>用户页</div> }));
vi.mock("./pages/UserLoginPage", () => ({ default: () => <div>普通用户登录页</div> }));
vi.mock("./pages/UserPortalPage", () => ({ default: () => <div>普通用户门户</div> }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1024 });
});

describe("application shell", () => {
  it("collapses desktop navigation and opens the account menu", async () => {
    api.me.mockResolvedValue({ username: "admin" });
    const { container } = render(<MemoryRouter><Shell /></MemoryRouter>);

    expect(await screen.findByText("仪表盘内容")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "切换导航" }));
    expect(container.querySelector(".ant-layout-sider-collapsed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /admin/ }));
    expect(await screen.findByText("退出登录")).toBeInTheDocument();
  });

  it("uses a drawer navigation on mobile", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    api.me.mockResolvedValue({ username: "admin" });
    render(<MemoryRouter><Shell /></MemoryRouter>);

    expect(await screen.findByText("仪表盘内容")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "打开导航" }));

    await waitFor(() => expect(document.querySelector(".ant-drawer-open .mobile-nav")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /节点/ })).toBeInTheDocument();
  });

  it("keeps the subscription user login separate from admin authentication", async () => {
    api.userMe.mockRejectedValue(new Error("not logged in"));
    render(<MemoryRouter initialEntries={["/user/login"]}><Shell /></MemoryRouter>);

    expect(await screen.findByText("普通用户登录页")).toBeInTheDocument();
    expect(api.me).not.toHaveBeenCalled();
    expect(api.userMe).toHaveBeenCalledWith({ suppressAuthEvent: true });
  });

  it("opens the user portal from the user login path when the user session is still valid", async () => {
    api.userMe.mockResolvedValue({ username: "demo" });
    render(<MemoryRouter initialEntries={["/user/login"]}><Shell /></MemoryRouter>);

    expect(await screen.findByText("普通用户门户")).toBeInTheDocument();
    expect(api.me).not.toHaveBeenCalled();
  });

  it("uses the subscription login as the default public entry", async () => {
    api.me.mockRejectedValue(new Error("not logged in"));
    api.userMe.mockRejectedValue(new Error("not logged in"));
    render(<MemoryRouter><Shell /></MemoryRouter>);

    expect(await screen.findByText("普通用户登录页")).toBeInTheDocument();
    expect(api.me).toHaveBeenCalledWith({ suppressAuthEvent: true });
    expect(api.userMe).toHaveBeenCalledWith({ suppressAuthEvent: true });
  });

  it("opens the user portal from the root path when the user session is still valid", async () => {
    api.me.mockRejectedValue(new Error("not admin"));
    api.userMe.mockResolvedValue({ username: "demo" });
    render(<MemoryRouter><Shell /></MemoryRouter>);

    expect(await screen.findByText("普通用户门户")).toBeInTheDocument();
  });

  it("does not confuse /users with the subscription user portal", async () => {
    api.me.mockResolvedValue({ username: "admin" });
    render(<MemoryRouter initialEntries={["/users"]}><Shell /></MemoryRouter>);

    expect(await screen.findByText("用户页")).toBeInTheDocument();
    expect(screen.queryByText("普通用户登录页")).not.toBeInTheDocument();
    expect(api.userMe).not.toHaveBeenCalled();
  });

  it("routes to the standalone clients page", async () => {
    api.me.mockResolvedValue({ username: "admin" });
    render(<MemoryRouter initialEntries={["/clients"]}><Shell /></MemoryRouter>);

    expect(await screen.findByText("客户端页")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /客户端/ })).toBeInTheDocument();
  });
});
