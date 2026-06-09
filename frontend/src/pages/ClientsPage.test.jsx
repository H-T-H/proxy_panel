import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import ClientsPage from "./ClientsPage";


vi.mock("../api/client", () => ({
  api: {
    getClientDownloadConfig: vi.fn(),
    listClientDownloads: vi.fn(),
    saveClientDownloadConfig: vi.fn(),
    updateClientDownload: vi.fn(),
  },
  pageData: (payload) => ({ items: payload.results, count: payload.count })
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ClientsPage", () => {
  it("renders fixed clients with upload-only file actions", async () => {
    api.getClientDownloadConfig.mockResolvedValue({
      enabled: true,
      platforms: [
        { key: "ios", label: "iOS", enabled: true },
        { key: "mac", label: "macOS", enabled: true },
        { key: "windows", label: "Windows", enabled: true },
        { key: "linux", label: "Linux", enabled: true },
        { key: "android", label: "Android", enabled: false }
      ]
    });
    api.listClientDownloads.mockResolvedValue({
      count: 3,
      results: [
        {
          id: 1,
          catalog_key: "shadowrocket_ios",
          name: "Shadowrocket",
          platform_code: "ios",
          platform: "iOS",
          version: "App Store",
          source_type: "external_link",
          delivery_mode: "link",
          download_url: "https://apps.apple.com/app/shadowrocket/id932747118",
          release_url: "",
          remote_url: "",
          auto_update_latest: false,
          file_available: false,
          has_local_file: false,
          file_name: "",
          enabled: true,
          sort_order: 10,
          remark: ""
        },
        {
          id: 2,
          catalog_key: "clash_verge_rev_linux",
          name: "Clash Verge Rev",
          platform_code: "linux",
          platform: "Linux",
          version: "v2.5.1",
          source_type: "remote_fetch",
          delivery_mode: "file",
          download_url: "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
          release_url: "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
          remote_url: "",
          auto_update_latest: true,
          file_available: true,
          has_local_file: true,
          file_name: "Clash.Verge_2.5.1_amd64.AppImage",
          enabled: true,
          sort_order: 20,
          remark: "Linux amd64"
        },
        {
          id: 3,
          catalog_key: "v2rayng_android",
          name: "v2rayNG",
          platform_code: "android",
          platform: "Android",
          version: "",
          source_type: "remote_fetch",
          delivery_mode: "link",
          download_url: "https://github.com/2dust/v2rayNG/releases/latest",
          release_url: "https://github.com/2dust/v2rayNG/releases/latest",
          remote_url: "",
          auto_update_latest: true,
          file_available: true,
          last_fetched_at: "",
          last_fetch_error: "",
          has_local_file: false,
          file_name: "",
          enabled: false,
          sort_order: 30,
          remark: "APK"
        }
      ]
    });

    render(<ClientsPage />);

    expect(await screen.findByRole("heading", { name: "客户端" })).toBeInTheDocument();
    expect(screen.getByText("用户页已显示")).toBeInTheDocument();
    expect(screen.getAllByText("macOS").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Windows").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Android").length).toBeGreaterThan(0);
    expect(screen.getByText("Shadowrocket")).toBeInTheDocument();
    expect(screen.getByText("Clash Verge Rev")).toBeInTheDocument();
    expect(screen.getByText("v2rayNG")).toBeInTheDocument();
    expect(screen.getAllByText("本地文件").length).toBeGreaterThan(0);
    expect(screen.getAllByText("链接").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "上传客户端文件" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "上传客户端文件" })[0]).toBeDisabled();
    expect(screen.queryByText("类型")).not.toBeInTheDocument();
    expect(screen.queryByText("添加客户端")).not.toBeInTheDocument();
  });
});
