import { Button, Form, Input, message } from "antd";
import { useState } from "react";

import { api, applyFormErrors } from "../api/client";


export default function LoginPage({ onLogin }) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  async function handleFinish(values) {
    setLoading(true);
    try {
      const user = await api.login(values);
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
    <div className="login-page">
      <div className="login-panel">
        <div className="login-title">ProxyPanel</div>
        <div className="login-subtitle">管理员后台</div>
        <Form form={form} layout="vertical" onFinish={handleFinish}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input autoFocus />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>登录</Button>
        </Form>
      </div>
    </div>
  );
}
