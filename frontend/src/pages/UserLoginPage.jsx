import { Alert, Button, Form, Input, message } from "antd";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { api, applyFormErrors } from "../api/client";


export default function UserLoginPage({ onLogin }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const location = useLocation();

  async function handleFinish(values) {
    setLoading(true);
    try {
      const user = await api.userLogin(values);
      message.success("登录成功");
      onLogin(user);
    } catch (error) {
      if (!applyFormErrors(form, error)) {
        message.error(error.message);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="user-login-page">
      <section className="user-login-panel" aria-labelledby="user-login-title">
        <div className="user-login-brand">ProxyPanel</div>
        <h1 id="user-login-title">登录订阅门户</h1>
        <p>查看订阅地址，复制或导入到客户端。</p>
        {location.state?.reason && (
          <Alert className="login-alert" type="warning" showIcon message={location.state.reason} />
        )}
        <Form form={form} layout="vertical" onFinish={handleFinish}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input autoFocus autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            进入订阅门户
          </Button>
        </Form>
        <div className="user-login-divider">管理员后台</div>
        <Link className="admin-login-link" to="/login">使用管理员账号登录</Link>
      </section>
    </main>
  );
}
