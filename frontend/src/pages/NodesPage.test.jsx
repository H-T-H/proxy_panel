import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import NodesPage from "./NodesPage";


vi.mock("../api/client", () => ({
  api: {
    listNodes: vi.fn(),
    nodeOptions: vi.fn(),
    bulkSetNodeState: vi.fn()
  },
  pageData: (payload) => ({ items: payload.results, count: payload.count })
}));

vi.mock("../components/YamlEditor", () => ({
  default: () => <textarea aria-label="YAML 编辑器" />
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NodesPage", () => {
  it("loads filters and performs a bulk disable", async () => {
    api.nodeOptions.mockResolvedValue({ types: ["ss"], sources: [{ id: 1, name: "Remote" }] });
    api.listNodes.mockResolvedValue({
      count: 1,
      results: [{
        id: 1,
        name: "HK 01",
        type: "ss",
        enabled: true,
        source_label: "Remote",
        tags: "",
        remark: "",
        config: { name: "HK 01", type: "ss" }
      }]
    });
    api.bulkSetNodeState.mockResolvedValue({ updated: 1, enabled: false });

    render(<MemoryRouter><NodesPage /></MemoryRouter>);
    expect(await screen.findByText("HK 01")).toBeInTheDocument();
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(screen.getByRole("button", { name: /禁用/ }));

    await waitFor(() => expect(api.bulkSetNodeState).toHaveBeenCalledWith([1], false));
  });
});
