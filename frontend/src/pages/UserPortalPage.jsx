import { Alert, Button, Input, Spin, Tag, Typography, message } from "antd";
import {
  CopyOutlined,
  ImportOutlined,
  LinkOutlined,
  LogoutOutlined
} from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";

const { Text } = Typography;


function clientLinkMeta(client) {
  const isAppStore = client.download_url?.includes("apps.apple.com");
  const icon = client.icon_url
    ? <img className="client-download-icon" src={client.icon_url} alt="" loading="lazy" referrerPolicy="no-referrer" />
    : <LinkOutlined />;
  if (client.delivery_mode === "file") {
    return {
      icon,
      detail: [
        "客户端文件",
        client.file_name || client.version
      ].filter(Boolean).join(" · ")
    };
  }
  return {
    icon,
    detail: isAppStore
      ? [client.platform, "App Store"].filter(Boolean).join(" · ")
      : [client.platform, client.version].filter(Boolean).join(" · ") || "客户端链接"
  };
}


function clientPlatformGroups(subscription) {
  if (subscription.client_platforms?.length) {
    return subscription.client_platforms;
  }
  return [{ key: "all", label: "客户端", items: subscription.client_downloads || [] }];
}


export default function UserPortalPage({ user, onLogout }) {
  const navigate = useNavigate();
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.userSubscription()
      .then(setSubscription)
      .catch((item) => setError(item.message))
      .finally(() => setLoading(false));
  }, []);

  async function copyText(text, successMessage = "订阅地址已复制") {
    try {
      await navigator.clipboard.writeText(text);
      message.success(successMessage);
      return true;
    } catch {
      message.error("复制失败，请手动复制");
      return false;
    }
  }

  function copyUrl() {
    copyText(subscription.subscription_url);
  }

  async function importClient(client) {
    if (client.requires_clipboard) {
      const copied = await copyText(
        client.clipboard_text || subscription.subscription_url,
        `${client.name} 订阅地址已复制`
      );
      if (copied && client.url) {
        window.open(client.url, "_self");
      }
    }
  }

  async function logout() {
    try {
      await api.userLogout();
    } finally {
      onLogout();
      navigate("/user/login", { replace: true });
    }
  }

  if (loading) {
    return <div className="center-screen"><Spin size="large" /></div>;
  }

  return (
    <main className="user-portal">
      <header className="user-portal-header">
        <div>
          <div className="user-login-brand">ProxyPanel</div>
          <h1>我的订阅</h1>
        </div>
        <Button icon={<LogoutOutlined />} onClick={logout}>退出登录</Button>
      </header>

      {error ? (
        <Alert type="error" showIcon message="加载订阅失败" description={error} />
      ) : (
        <div className="portal-content">
          <section className="account-summary" aria-label="账号信息">
            <div><Text type="secondary">当前用户</Text><strong>{user.username}</strong></div>
            <div><Text type="secondary">账号状态</Text><Tag color="success">已启用</Tag></div>
            <div><Text type="secondary">可用节点</Text><strong>{subscription.node_count}</strong></div>
          </section>

          {subscription.remark && <Alert type="info" showIcon message={subscription.remark} />}
          {subscription.node_count === 0 && (
            <Alert
              type="warning"
              showIcon
              message="当前没有可用节点"
              description="请联系管理员为账号绑定并启用节点。"
            />
          )}

          <section className="subscription-section" aria-labelledby="subscription-url-title">
            <h2 id="subscription-url-title">订阅地址</h2>
            <div className="subscription-copy-row">
              <Input className="subscription-url-input" readOnly value={subscription.subscription_url} />
              <Button type="primary" icon={<CopyOutlined />} onClick={copyUrl}>复制</Button>
            </div>
          </section>

          <section className="subscription-section" aria-labelledby="import-title">
            <h2 id="import-title">一键导入客户端</h2>
            <div className="import-actions">
              {subscription.import_links.map((client) => (
                client.available ? (
                  client.requires_clipboard ? (
                    <Button
                      key={client.key}
                      icon={<ImportOutlined />}
                      onClick={() => importClient(client)}
                      disabled={subscription.node_count === 0}
                    >
                      {client.name}
                    </Button>
                  ) : (
                    <Button
                      key={client.key}
                      icon={<ImportOutlined />}
                      href={client.url}
                      disabled={subscription.node_count === 0}
                    >
                      {client.name}
                    </Button>
                  )
                ) : (
                  <Button key={client.key} disabled>{client.name}（暂不可用）</Button>
                )
              ))}
            </div>
          </section>

          {subscription.client_downloads_enabled && subscription.client_downloads?.length > 0 && (
            <section className="subscription-section" aria-labelledby="download-client-title">
              <h2 id="download-client-title">获取客户端</h2>
              <div className="client-platform-groups">
                {clientPlatformGroups(subscription).map((group) => (
                  <div key={group.key} className="client-platform-group">
                    <h3>{group.label}</h3>
                    <div className="client-download-actions">
                      {group.items.map((client) => {
                        const meta = clientLinkMeta(client);
                        return (
                          <a
                            key={client.id}
                            className="client-download-button"
                            href={client.download_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {meta.icon}
                            <span>
                              <strong>{client.name}</strong>
                              <small>{meta.detail}</small>
                            </span>
                          </a>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
