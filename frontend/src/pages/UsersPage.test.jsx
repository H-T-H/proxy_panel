import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import UsersPage from "./UsersPage";


vi.mock("../api/client", () => ({
  api: {
    listUsers: vi.fn(),
    listNodes: vi.fn(),
    nodeOptions: vi.fn(),
    resetUserToken: vi.fn()
  },
  applyFormErrors: vi.fn(() => false),
  pageData: (payload) => ({ items: payload.results, count: payload.count })
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UsersPage", () => {
  it("shows the subscription URL with only copy beside it and the new URL after token reset", async () => {
    api.listUsers.mockResolvedValue({
      count: 1,
      results: [{
        id: 7,
        username: "alice",
        remark: "",
        node_count: 2,
        enabled: true,
        node_ids: [],
        subscription_path: "/sub/old-token"
      }]
    });
    api.resetUserToken.mockResolvedValue({
      username: "alice",
      subscription_path: "/sub/new-token"
    });

    render(<ConfigProvider locale={zhCN}><UsersPage /></ConfigProvider>);

    expect(await screen.findByText("http://localhost:3000/sub/old-token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "打开订阅" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "下载订阅" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重置 Token" }));
    fireEvent.click(await screen.findByRole("button", { name: /确\s*定/ }));

    await waitFor(() => expect(api.resetUserToken).toHaveBeenCalledWith(7));
    expect(await screen.findByDisplayValue("http://localhost:3000/sub/new-token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制新订阅地址" })).toBeInTheDocument();
  });
});
