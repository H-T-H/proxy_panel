import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import SettingsPage from "./SettingsPage";


vi.mock("../api/client", () => ({
  api: {
    getTemplate: vi.fn(),
    listUsers: vi.fn(),
    previewTemplate: vi.fn(),
    saveTemplate: vi.fn(),
    restoreTemplate: vi.fn(),
    getClientDownloadConfig: vi.fn(),
    saveClientDownloadConfig: vi.fn(),
    listClientDownloads: vi.fn(),
    createClientDownload: vi.fn(),
    updateClientDownload: vi.fn(),
    deleteClientDownload: vi.fn(),
    syncClientDownloadLatest: vi.fn()
  },
  pageData: (payload) => ({ items: payload.results, count: payload.count })
}));

vi.mock("../components/YamlEditor", () => ({
  default: ({ value, onChange }) => (
    <textarea aria-label="YAML 编辑器" value={value} onChange={(event) => onChange(event.target.value)} />
  )
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SettingsPage", () => {
  it("validates YAML and previews the generated subscription", async () => {
    api.getTemplate.mockResolvedValue({
      template: "mixed-port: 7890\nproxies: __PROXIES__",
      node_order_keywords: "香港\n日本",
      remote_url: "",
      remote_updated_at: ""
    });
    api.listUsers.mockResolvedValue({ count: 0, results: [] });
    api.getClientDownloadConfig.mockResolvedValue({ enabled: false });
    api.listClientDownloads.mockResolvedValue({ count: 0, results: [] });
    api.previewTemplate.mockResolvedValue({
      node_count: 1,
      yaml: "mixed-port: 7890\nproxies:\n  - name: HK"
    });

    render(<SettingsPage />);

    const editor = await screen.findByLabelText("YAML 编辑器");
    fireEvent.change(editor, { target: { value: "broken: [" } });
    expect(await screen.findByText(/第 2 行/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存模板" })).toBeDisabled();

    fireEvent.change(editor, { target: { value: "mixed-port: 7890\nproxies: __PROXIES__" } });
    fireEvent.click(screen.getByRole("button", { name: /设置顺序/ }));
    fireEvent.change(await screen.findByPlaceholderText("输入节点名称关键词，如 香港"), { target: { value: "美国" } });
    fireEvent.click(screen.getByRole("button", { name: /添加/ }));
    fireEvent.click(screen.getByRole("button", { name: /应\s*用/ }));
    fireEvent.click(screen.getByRole("button", { name: /预览订阅/ }));

    await waitFor(() => expect(api.previewTemplate).toHaveBeenCalledWith({
      template: "mixed-port: 7890\nproxies: __PROXIES__",
      node_order_keywords: "香港\n日本\n美国"
    }));
    expect(await screen.findByText(/- name: HK/)).toBeInTheDocument();
  });
});
