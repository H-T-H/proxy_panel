import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import NotFoundPage from "./NotFoundPage";


describe("NotFoundPage", () => {
  it("offers a route back to the dashboard", () => {
    render(<MemoryRouter><NotFoundPage /></MemoryRouter>);
    expect(screen.getByText("页面不存在")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回仪表盘" })).toHaveAttribute("href", "/");
  });
});
