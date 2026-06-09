import React, { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { App as AntApp, Avatar, Button, ConfigProvider, Drawer, Dropdown, Layout, Menu, Spin, Tooltip, theme } from "antd";
import {
  ApiOutlined,
  AppstoreOutlined,
  ClusterOutlined,
  DashboardOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  UserOutlined
} from "@ant-design/icons";
import zhCN from "antd/locale/zh_CN";
import "antd/dist/reset.css";
import "./styles/app.css";

import { api } from "./api/client";

const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ClientsPage = lazy(() => import("./pages/ClientsPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const NodesPage = lazy(() => import("./pages/NodesPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const SourcesPage = lazy(() => import("./pages/SourcesPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));
const UserLoginPage = lazy(() => import("./pages/UserLoginPage"));
const UserPortalPage = lazy(() => import("./pages/UserPortalPage"));

const { Header, Content, Sider } = Layout;


function AdminShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(window.innerWidth < 768);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    function resize() {
      setMobile(window.innerWidth < 768);
    }
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    function requireLogin(event) {
      setUser(null);
      navigate("/login", { state: { reason: event.detail?.message } });
    }
    window.addEventListener("proxypanel:auth-required", requireLogin);
    return () => window.removeEventListener("proxypanel:auth-required", requireLogin);
  }, [navigate]);

  const menuItems = useMemo(() => [
    { key: "dashboard", icon: <DashboardOutlined />, label: <Link to="/">仪表盘</Link> },
    { key: "sources", icon: <ApiOutlined />, label: <Link to="/sources">订阅源</Link> },
    { key: "nodes", icon: <ClusterOutlined />, label: <Link to="/nodes">节点</Link> },
    { key: "users", icon: <UserOutlined />, label: <Link to="/users">用户</Link> },
    { key: "clients", icon: <AppstoreOutlined />, label: <Link to="/clients">客户端</Link> },
    { key: "settings", icon: <SettingOutlined />, label: <Link to="/settings">模板设置</Link> }
  ], []);

  if (loading) {
    return <div className="center-screen"><Spin size="large" /></div>;
  }
  if (!user && location.pathname !== "/login") {
    return <Navigate to={location.pathname === "/" ? "/user/login" : "/login"} replace />;
  }
  if (location.pathname === "/login") {
    return (
      <LoginPage
        onLogin={(loggedInUser) => {
          setUser(loggedInUser);
          navigate("/", { replace: true });
        }}
      />
    );
  }

  const current = location.pathname.split("/")[1] || "dashboard";
  const nav = (
    <>
      <div className={`brand ${collapsed && !mobile ? "brand-collapsed" : ""}`}>
        <span className="brand-mark">P</span>
        {(mobile || !collapsed) && <span>ProxyPanel</span>}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[current]}
        items={menuItems}
        onClick={() => setDrawerOpen(false)}
      />
    </>
  );

  async function handleLogout() {
    try {
      await api.logout();
    } finally {
      setUser(null);
      navigate("/login");
    }
  }

  return (
    <Layout className="app-shell">
      {!mobile && (
        <Sider className="app-sider" width={232} collapsedWidth={72} collapsed={collapsed} trigger={null}>
          {nav}
        </Sider>
      )}
      <Drawer
        className="mobile-nav"
        width={256}
        placement="left"
        open={mobile && drawerOpen}
        onClose={() => setDrawerOpen(false)}
        styles={{ body: { padding: 0, background: "#18202f" } }}
      >
        {nav}
      </Drawer>
      <Layout className="main-layout">
        <Header className="app-header">
          <Tooltip title={mobile ? "打开导航" : collapsed ? "展开导航" : "收起导航"}>
            <Button
              type="text"
              aria-label={mobile ? "打开导航" : "切换导航"}
              icon={mobile ? <MenuOutlined /> : collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => mobile ? setDrawerOpen(true) : setCollapsed(!collapsed)}
            />
          </Tooltip>
          <div className="header-spacer" />
          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                { key: "account", label: user.username, disabled: true },
                { type: "divider" },
                { key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: handleLogout }
              ]
            }}
          >
            <Button type="text" className="account-button">
              <Avatar size={28} icon={<UserOutlined />} />
              <span>{user.username}</span>
            </Button>
          </Dropdown>
        </Header>
        <Content className="app-content">
          <Suspense fallback={<div className="page-loader"><Spin size="large" /></div>}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/sources" element={<SourcesPage />} />
              <Route path="/nodes" element={<NodesPage />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/clients" element={<ClientsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  );
}

function UserShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.userMe({ suppressAuthEvent: true })
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, [location.pathname]);

  useEffect(() => {
    function requireLogin(event) {
      setUser(null);
      navigate("/user/login", {
        replace: true,
        state: { reason: event.detail?.message || "会话已失效，请重新登录" }
      });
    }
    window.addEventListener("proxypanel:user-auth-required", requireLogin);
    return () => window.removeEventListener("proxypanel:user-auth-required", requireLogin);
  }, [navigate]);

  if (loading) {
    return <div className="center-screen"><Spin size="large" /></div>;
  }
  if (location.pathname === "/user/login") {
    if (user) {
      return <Navigate to="/user" replace />;
    }
    return (
      <Suspense fallback={<div className="center-screen"><Spin size="large" /></div>}>
        <UserLoginPage onLogin={(loggedInUser) => {
          setUser(loggedInUser);
          navigate("/user", { replace: true });
        }} />
      </Suspense>
    );
  }
  if (!user) {
    return <Navigate to="/user/login" replace />;
  }
  return (
    <Suspense fallback={<div className="center-screen"><Spin size="large" /></div>}>
      <Routes>
        <Route path="/user" element={<UserPortalPage user={user} onLogout={() => setUser(null)} />} />
        <Route path="*" element={<Navigate to="/user" replace />} />
      </Routes>
    </Suspense>
  );
}

function RootEntry() {
  const [target, setTarget] = useState("");

  useEffect(() => {
    let active = true;
    async function resolveEntry() {
      try {
        await api.me({ suppressAuthEvent: true });
        if (active) {
          setTarget("admin");
        }
        return;
      } catch {
        // Fall through to the subscription user session check.
      }
      try {
        await api.userMe({ suppressAuthEvent: true });
        if (active) {
          setTarget("/user");
        }
      } catch {
        if (active) {
          setTarget("/user/login");
        }
      }
    }
    resolveEntry();
    return () => {
      active = false;
    };
  }, []);

  if (!target) {
    return <div className="center-screen"><Spin size="large" /></div>;
  }
  if (target === "admin") {
    return <AdminShell />;
  }
  return <Navigate to={target} replace />;
}

export function Shell() {
  const location = useLocation();
  if (location.pathname === "/") {
    return <RootEntry />;
  }
  const userPortalPath = location.pathname === "/user" || location.pathname.startsWith("/user/");
  return userPortalPath ? <UserShell /> : <AdminShell />;
}


const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            borderRadius: 6,
            colorPrimary: "#2563eb",
            colorBgLayout: "#f3f5f8",
            fontSize: 14
          },
          components: {
            Table: { headerBg: "#f8fafc", cellPaddingBlock: 12 },
            Menu: { darkItemBg: "#18202f", darkSubMenuItemBg: "#18202f" }
          }
        }}
      >
        <AntApp>
          <BrowserRouter>
            <Shell />
          </BrowserRouter>
        </AntApp>
      </ConfigProvider>
    </React.StrictMode>
  );
}
