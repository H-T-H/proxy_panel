const API_BASE = import.meta.env.VITE_API_BASE || "";

export class ApiError extends Error {
  constructor(message, fields = {}) {
    super(message);
    this.name = "ApiError";
    this.fields = fields;
  }
}

function errorText(value) {
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(errorText).filter(Boolean).join("，");
  }
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => key === "detail" || key === "non_field_errors" ? errorText(item) : `${key}: ${errorText(item)}`)
      .filter(Boolean)
      .join("；");
  }
  return "";
}

async function request(path, options = {}) {
  const { suppressAuthEvent = false, ...fetchOptions } = options;
  const isFormData = fetchOptions.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(fetchOptions.headers || {})
  };

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      ...fetchOptions,
      headers
    });
  } catch {
    throw new Error("网络连接失败，请检查服务状态");
  }

  if (!response.ok) {
    let message = response.statusText;
    let fields = {};
    try {
      const body = await response.text();
      try {
        const parsed = JSON.parse(body);
        message = errorText(parsed) || message;
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          fields = Object.fromEntries(
            Object.entries(parsed)
              .filter(([key]) => !["detail", "non_field_errors"].includes(key))
              .map(([key, value]) => [key, errorText(value)])
          );
        }
      } catch {
        message = body || message;
      }
    } catch {
      message = response.statusText;
    }
    if (!suppressAuthEvent && (response.status === 401 || response.status === 403) && !path.endsWith("/login/")) {
      const userPortalRequest = path.startsWith("/api/user-auth/") || path.startsWith("/api/user/");
      window.dispatchEvent(new CustomEvent(
        userPortalRequest ? "proxypanel:user-auth-required" : "proxypanel:auth-required",
        { detail: { message } }
      ));
    }
    throw new ApiError(message || "请求失败", fields);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}


function qs(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, value);
    }
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}


export const api = {
  login: (payload) => request("/api/auth/login/", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request("/api/auth/logout/", { method: "POST", body: "{}" }),
  me: (options) => request("/api/auth/me/", options),
  dashboard: () => request("/api/dashboard/"),
  listClientDownloads: (params) => request(`/api/client-downloads/${qs(params)}`),
  createClientDownload: (payload) => request("/api/client-downloads/", {
    method: "POST",
    body: payload instanceof FormData ? payload : JSON.stringify(payload)
  }),
  updateClientDownload: (id, payload) => request(`/api/client-downloads/${id}/`, {
    method: "PATCH",
    body: payload instanceof FormData ? payload : JSON.stringify(payload)
  }),
  deleteClientDownload: (id) => request(`/api/client-downloads/${id}/`, { method: "DELETE" }),
  syncClientDownloadLatest: (id) => request(`/api/client-downloads/${id}/sync-latest/`, { method: "POST", body: "{}" }),
  fetchClientDownloadRemote: (id) => request(`/api/client-downloads/${id}/fetch-remote/`, { method: "POST", body: "{}" }),
  getClientDownloadConfig: () => request("/api/client-downloads/config/"),
  saveClientDownloadConfig: (enabled, platforms) => request(
    "/api/client-downloads/config/",
    { method: "POST", body: JSON.stringify({ enabled, ...(platforms ? { platforms } : {}) }) }
  ),
  listSources: (params) => request(`/api/sources/${qs(params)}`),
  createSource: (payload) => request("/api/sources/", { method: "POST", body: JSON.stringify(payload) }),
  updateSource: (id, payload) => request(`/api/sources/${id}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSource: (id) => request(`/api/sources/${id}/`, { method: "DELETE" }),
  syncSource: (id) => request(`/api/sources/${id}/sync/`, { method: "POST", body: "{}" }),
  bulkSyncSources: (ids) => request("/api/sources/bulk-sync/", { method: "POST", body: JSON.stringify({ ids }) }),
  listNodes: (params) => request(`/api/nodes/${qs(params)}`),
  nodeOptions: () => request("/api/nodes/options/"),
  previewNode: (node_text) => request("/api/nodes/preview/", { method: "POST", body: JSON.stringify({ node_text }) }),
  createManualNode: (node_text) => request("/api/nodes/manual/", { method: "POST", body: JSON.stringify({ node_text }) }),
  updateNode: (id, payload) => request(`/api/nodes/${id}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteNode: (id) => request(`/api/nodes/${id}/`, { method: "DELETE" }),
  toggleNode: (id) => request(`/api/nodes/${id}/toggle/`, { method: "POST", body: "{}" }),
  bulkDeleteNodes: (ids) => request("/api/nodes/bulk-delete/", { method: "POST", body: JSON.stringify({ ids }) }),
  bulkSetNodeState: (ids, enabled) => request("/api/nodes/bulk-state/", { method: "POST", body: JSON.stringify({ ids, enabled }) }),
  listUsers: (params) => request(`/api/users/${qs(params)}`),
  createUser: (payload) => request("/api/users/", { method: "POST", body: JSON.stringify(payload) }),
  updateUser: (id, payload) => request(`/api/users/${id}/`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteUser: (id) => request(`/api/users/${id}/`, { method: "DELETE" }),
  resetUserToken: (id) => request(`/api/users/${id}/reset-token/`, { method: "POST", body: "{}" }),
  getTemplate: () => request("/api/settings/template/"),
  saveTemplate: (template, node_order_keywords = "") => request(
    "/api/settings/template/",
    { method: "POST", body: JSON.stringify({ template, node_order_keywords }) }
  ),
  extractTemplate: (config_text) => request("/api/settings/template/extract/", { method: "POST", body: JSON.stringify({ config_text }) }),
  fetchTemplate: (remote_url) => request("/api/settings/template/fetch/", { method: "POST", body: JSON.stringify({ remote_url }) }),
  previewTemplate: (payload) => request("/api/settings/template/preview/", { method: "POST", body: JSON.stringify(payload) }),
  restoreTemplate: () => request("/api/settings/template/restore/", { method: "POST", body: "{}" }),
  userLogin: (payload) => request("/api/user-auth/login/", { method: "POST", body: JSON.stringify(payload) }),
  userLogout: () => request("/api/user-auth/logout/", { method: "POST", body: "{}" }),
  userMe: (options) => request("/api/user-auth/me/", options),
  userSubscription: () => request("/api/user/subscription/")
};


export function pageData(payload) {
  return {
    items: payload?.results || [],
    count: payload?.count || 0
  };
}


export function applyFormErrors(form, error) {
  const entries = Object.entries(error?.fields || {});
  if (!entries.length) {
    return false;
  }
  form.setFields(entries.map(([name, errors]) => ({ name, errors: [errors] })));
  return true;
}
