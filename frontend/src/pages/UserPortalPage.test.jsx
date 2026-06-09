import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import UserPortalPage from "./UserPortalPage";


vi.mock("../api/client", () => ({
  api: {
    userSubscription: vi.fn(),
    userLogout: vi.fn()
  }
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("UserPortalPage", () => {
  it("renders the subscription URL with only copy beside it, import links, and logs out", async () => {
    api.userSubscription.mockResolvedValue({
      username: "alice",
      enabled: true,
      remark: "",
      node_count: 2,
      subscription_url: "http://localhost/sub/token",
      download_url: "http://localhost/sub/token?download=1",
      client_downloads_enabled: true,
      client_downloads: [
        {
          id: 1,
          name: "Shadowrocket",
          platform_code: "ios",
          platform: "iOS",
          version: "App Store",
          download_url: "https://apps.apple.com/app/shadowrocket/id932747118"
        }
      ],
      client_platforms: [
        {
          key: "ios",
          label: "iOS",
          items: [
            {
              id: 1,
              name: "Shadowrocket",
              platform_code: "ios",
              platform: "iOS",
              version: "App Store",
              source_type: "external_link",
              download_url: "https://apps.apple.com/app/shadowrocket/id932747118"
            }
          ]
        }
      ],
      import_links: [
        { key: "clash_verge", name: "Clash Verge", url: "clash://install-config?url=x", available: true },
        {
          key: "shadowrocket",
          name: "Shadowrocket",
          url: "shadowrocket://",
          available: true,
          requires_clipboard: true,
          clipboard_text: "http://localhost/sub/token"
        }
      ]
    });
    api.userLogout.mockResolvedValue({ ok: true });
    const onLogout = vi.fn();
    const clipboard = { writeText: vi.fn().mockResolvedValue() };
    vi.stubGlobal("open", vi.fn());
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: clipboard });

    render(
      <ConfigProvider locale={zhCN}>
        <MemoryRouter initialEntries={["/user"]}>
          <UserPortalPage user={{ username: "alice" }} onLogout={onLogout} />
        </MemoryRouter>
      </ConfigProvider>
    );

    expect(await screen.findByDisplayValue("http://localhost/sub/token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /复制/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /打开订阅/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /下载 YAML/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Clash Verge/ })).toHaveAttribute(
      "href",
      "clash://install-config?url=x"
    );
    expect(screen.getByRole("heading", { name: "iOS" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Shadowrocket iOS · App Store/ })).toHaveAttribute(
      "href",
      "https://apps.apple.com/app/shadowrocket/id932747118"
    );
    expect(screen.getByRole("button", { name: /Shadowrocket/ })).not.toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /复制/ }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith("http://localhost/sub/token"));

    fireEvent.click(screen.getByRole("button", { name: /Shadowrocket/ }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith("http://localhost/sub/token"));
    expect(window.open).toHaveBeenCalledWith("shadowrocket://", "_self");

    fireEvent.click(screen.getByRole("button", { name: /退出登录/ }));
    await waitFor(() => expect(api.userLogout).toHaveBeenCalledOnce());
    expect(onLogout).toHaveBeenCalledOnce();
  });
});
