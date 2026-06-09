import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, pageData } from "./client";


function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}


describe("API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("adds pagination parameters", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ count: 0, results: [] }));
    await api.listNodes({ page: 2, page_size: 50, search: "HK" });
    expect(fetch.mock.calls[0][0]).toBe("/api/nodes/?page=2&page_size=50&search=HK");
  });

  it("sends write requests directly", async () => {
    fetch.mockImplementation(() => Promise.resolve(jsonResponse({ ok: true })));
    await api.logout();
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0][0]).toBe("/api/auth/logout/");
    expect(fetch.mock.calls[0][1].headers).toEqual({ "Content-Type": "application/json" });
  });

  it("formats DRF field errors", async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ username: ["已存在"], node_ids: ["无效节点"] }, 400));
    const error = await api.createUser({ username: "alice" }).catch((item) => item);
    expect(error.message).toBe("username: 已存在；node_ids: 无效节点");
    expect(error.fields).toEqual({ username: "已存在", node_ids: "无效节点" });
  });

  it("announces expired sessions", async () => {
    const listener = vi.fn();
    window.addEventListener("proxypanel:auth-required", listener);
    fetch.mockResolvedValueOnce(jsonResponse({ detail: "身份认证信息未提供。" }, 403));
    await expect(api.listUsers()).rejects.toThrow("身份认证信息未提供。");
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0].detail.message).toBe("身份认证信息未提供。");
    window.removeEventListener("proxypanel:auth-required", listener);
  });

  it("announces subscription user session expiry separately", async () => {
    const adminListener = vi.fn();
    const userListener = vi.fn();
    window.addEventListener("proxypanel:auth-required", adminListener);
    window.addEventListener("proxypanel:user-auth-required", userListener);
    fetch.mockResolvedValueOnce(jsonResponse({ detail: "普通用户会话已失效" }, 401));

    await expect(api.userSubscription()).rejects.toThrow("普通用户会话已失效");
    expect(userListener).toHaveBeenCalledOnce();
    expect(adminListener).not.toHaveBeenCalled();

    window.removeEventListener("proxypanel:auth-required", adminListener);
    window.removeEventListener("proxypanel:user-auth-required", userListener);
  });

  it("normalizes paginated payloads", () => {
    expect(pageData({ count: 2, results: [{ id: 1 }] })).toEqual({
      count: 2,
      items: [{ id: 1 }]
    });
  });
});
