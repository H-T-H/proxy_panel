import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { message } from "antd";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CopyButton, DateTime, EmptyState, PageHeader } from "./Common";


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("common UI", () => {
  it("renders the shared page header and empty action", () => {
    render(
      <>
        <PageHeader title="节点" description="节点管理" actions={<button>新增</button>} />
        <EmptyState title="没有节点" actions={<button>同步</button>} />
      </>
    );
    expect(screen.getByRole("heading", { name: "节点" })).toBeInTheDocument();
    expect(screen.getByText("节点管理")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "同步" })).toBeInTheDocument();
  });

  it("copies text with feedback", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const success = vi.spyOn(message, "success").mockImplementation(() => {});
    render(<CopyButton text="https://example.com/sub/token" />);
    fireEvent.click(screen.getByRole("button", { name: "复制" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("https://example.com/sub/token"));
    expect(success).toHaveBeenCalled();
  });

  it("formats local dates and empty dates", () => {
    const { rerender } = render(<DateTime value={null} />);
    expect(screen.getByText("未同步")).toBeInTheDocument();
    rerender(<DateTime value="2026-06-06T12:00:00Z" />);
    expect(screen.queryByText("未同步")).not.toBeInTheDocument();
  });
});
