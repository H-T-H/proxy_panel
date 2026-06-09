import { Alert, Button, Empty, Form, Input, Modal, Select, Tabs, Tag, message } from "antd";
import {
  CheckCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  HolderOutlined,
  OrderedListOutlined,
  PlusOutlined,
  ReloadOutlined
} from "@ant-design/icons";
import yaml from "js-yaml";
import { useEffect, useMemo, useState } from "react";

import { api, pageData } from "../api/client";
import { DateTime, PageHeader, WorkSurface } from "../components/Common";
import YamlEditor from "../components/YamlEditor";

const { TextArea } = Input;

function parseOrderKeywords(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatOrderKeywords(items) {
  return items.map((item) => item.trim()).filter(Boolean).join("\n");
}


export default function SettingsPage() {
  const [template, setTemplate] = useState("");
  const [savedTemplate, setSavedTemplate] = useState("");
  const [nodeOrderKeywords, setNodeOrderKeywords] = useState("");
  const [savedNodeOrderKeywords, setSavedNodeOrderKeywords] = useState("");
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [orderDraft, setOrderDraft] = useState([]);
  const [orderInput, setOrderInput] = useState("");
  const [dragIndex, setDragIndex] = useState(null);
  const [remoteMeta, setRemoteMeta] = useState({ remote_url: "", remote_updated_at: "" });
  const [users, setUsers] = useState([]);
  const [previewUser, setPreviewUser] = useState("");
  const [preview, setPreview] = useState(null);
  const [yamlError, setYamlError] = useState("");
  const [loading, setLoading] = useState(false);
  const [remoteForm] = Form.useForm();
  const [extractForm] = Form.useForm();
  const dirty = template !== savedTemplate || nodeOrderKeywords !== savedNodeOrderKeywords;

  async function load() {
    try {
      const [data, userData] = await Promise.all([
        api.getTemplate(),
        api.listUsers({ page_size: 100 })
      ]);
      setTemplate(data.template || "");
      setSavedTemplate(data.template || "");
      setNodeOrderKeywords(data.node_order_keywords || "");
      setSavedNodeOrderKeywords(data.node_order_keywords || "");
      setRemoteMeta(data);
      remoteForm.setFieldsValue({ remote_url: data.remote_url });
      setUsers(pageData(userData).items);
    } catch (error) {
      message.error(error.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    function beforeUnload(event) {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    }
    function interceptLink(event) {
      const anchor = event.target.closest?.("a[href]");
      if (dirty && anchor && anchor.origin === window.location.origin && !window.confirm("模板有未保存修改，确定离开吗？")) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", interceptLink, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", interceptLink, true);
    };
  }, [dirty]);

  function validate(value) {
    setTemplate(value);
    try {
      const data = yaml.load(value);
      if (!data || typeof data !== "object" || Array.isArray(data)) {
        throw new Error("模板顶层必须是 YAML 对象");
      }
      setYamlError("");
    } catch (error) {
      setYamlError(error.mark ? `第 ${error.mark.line + 1} 行，第 ${error.mark.column + 1} 列：${error.reason}` : error.message);
    }
  }

  async function save() {
    try {
      const parsed = yaml.load(template);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("模板顶层必须是 YAML 对象");
      }
      setYamlError("");
    } catch (error) {
      setYamlError(error.mark ? `第 ${error.mark.line + 1} 行，第 ${error.mark.column + 1} 列：${error.reason}` : error.message);
      return;
    }
    setLoading(true);
    try {
      await api.saveTemplate(template, nodeOrderKeywords);
      setSavedTemplate(template);
      setSavedNodeOrderKeywords(nodeOrderKeywords);
      message.success("模板已保存");
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function showPreview() {
    setLoading(true);
    try {
      const result = await api.previewTemplate({
        template,
        node_order_keywords: nodeOrderKeywords,
        ...(previewUser ? { user_id: Number(previewUser) } : {})
      });
      setPreview(result);
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  function confirmReplacement(nextTemplate, sourceLabel) {
    Modal.confirm({
      title: "覆盖当前模板？",
      content: `将使用${sourceLabel}提取出的模板替换编辑器内容，保存前仍可撤销或离开页面。`,
      okText: "确认覆盖",
      cancelText: "取消",
      onOk: () => {
        validate(nextTemplate);
        message.success("已载入提取结果，请预览并保存");
      }
    });
  }

  async function fetchRemote(values) {
    setLoading(true);
    try {
      const data = await api.fetchTemplate(values.remote_url);
      confirmReplacement(data.template, "远程配置");
      setRemoteMeta({
        remote_url: values.remote_url,
        remote_updated_at: new Date().toISOString()
      });
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function extract(values) {
    setLoading(true);
    try {
      const data = await api.extractTemplate(values.config_text);
      confirmReplacement(data.template, "粘贴配置");
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function restore() {
    setLoading(true);
    try {
      const result = await api.restoreTemplate();
      setTemplate(result.template);
      setSavedTemplate(result.template);
      setNodeOrderKeywords(result.node_order_keywords || "");
      setSavedNodeOrderKeywords(result.node_order_keywords || "");
      setYamlError("");
      message.success("已恢复并保存默认模板");
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  function openOrderModal() {
    setOrderDraft(parseOrderKeywords(nodeOrderKeywords));
    setOrderInput("");
    setDragIndex(null);
    setOrderModalOpen(true);
  }

  function addOrderKeyword() {
    const keyword = orderInput.trim();
    if (!keyword) {
      return;
    }
    if (orderDraft.includes(keyword)) {
      message.warning("该节点关键词已存在");
      return;
    }
    setOrderDraft([...orderDraft, keyword]);
    setOrderInput("");
  }

  function removeOrderKeyword(index) {
    setOrderDraft(orderDraft.filter((_, itemIndex) => itemIndex !== index));
  }

  function moveOrderKeyword(fromIndex, toIndex) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) {
      return;
    }
    const nextItems = [...orderDraft];
    const [item] = nextItems.splice(fromIndex, 1);
    nextItems.splice(toIndex, 0, item);
    setOrderDraft(nextItems);
  }

  function applyOrderKeywords() {
    setNodeOrderKeywords(formatOrderKeywords(orderDraft));
    setOrderModalOpen(false);
  }

  const validationTag = useMemo(() => yamlError
    ? <Tag color="error">YAML 有错误</Tag>
    : <Tag color="success" icon={<CheckCircleOutlined />}>YAML 有效</Tag>, [yamlError]);
  const orderKeywords = useMemo(() => parseOrderKeywords(nodeOrderKeywords), [nodeOrderKeywords]);

  return (
    <>
      <PageHeader
        title="模板设置"
        description="编辑订阅模板，并在保存前检查最终生成结果。"
        meta={<>{validationTag}{dirty && <Tag color="warning">未保存</Tag>}</>}
        actions={[
          <Button key="preview" icon={<EyeOutlined />} loading={loading} onClick={showPreview}>预览订阅</Button>,
          <Button key="save" type="primary" loading={loading} disabled={!!yamlError || !dirty} onClick={save}>保存模板</Button>
        ]}
      />
      <WorkSurface>
        <Tabs
          className="settings-tabs"
          items={[
            {
              key: "editor",
              label: "模板编辑",
              children: (
                <div className="settings-pane">
                  {yamlError && <Alert type="error" showIcon message={yamlError} />}
                  <div className="preview-selector">
                    <span>预览范围</span>
                    <Select
                      value={previewUser}
                      style={{ minWidth: 220 }}
                      options={[
                        { value: "", label: "全部启用节点" },
                        ...users.map((user) => ({ value: String(user.id), label: `${user.username}（${user.node_count} 节点）` }))
                      ]}
                      onChange={setPreviewUser}
                    />
                  </div>
                  <div className="node-order-toolbar">
                    <div className="node-order-summary">
                      <span className="node-order-label">节点顺序</span>
                      <div className="node-order-tags">
                        {orderKeywords.length ? (
                          <>
                            {orderKeywords.slice(0, 5).map((keyword) => <Tag key={keyword}>{keyword}</Tag>)}
                            {orderKeywords.length > 5 && <Tag>+{orderKeywords.length - 5}</Tag>}
                          </>
                        ) : (
                          <span className="muted-text">默认按节点列表顺序输出</span>
                        )}
                      </div>
                    </div>
                    <Button icon={<OrderedListOutlined />} onClick={openOrderModal}>设置顺序</Button>
                  </div>
                  <YamlEditor value={template} onChange={validate} minHeight="520px" />
                  <div className="settings-footer">
                    <Button
                      danger
                      icon={<ReloadOutlined />}
                      loading={loading}
                      onClick={() => Modal.confirm({
                        title: "恢复默认模板？",
                        content: "当前模板将被默认配置替换并立即保存。",
                        okText: "恢复默认",
                        okButtonProps: { danger: true },
                        onOk: restore
                      })}
                    >
                      恢复默认模板
                    </Button>
                  </div>
                </div>
              )
            },
            {
              key: "remote",
              label: "远程提取",
              forceRender: true,
              children: (
                <div className="settings-pane narrow-pane">
                  <Alert
                    showIcon
                    type="info"
                    message="从完整 Clash 配置中移除节点，并将节点位置替换为模板占位符。"
                  />
                  <Form form={remoteForm} layout="vertical" onFinish={fetchRemote}>
                    <Form.Item name="remote_url" label="远程配置 URL" rules={[{ required: true }, { type: "url" }]}>
                      <Input placeholder="https://example.com/config.yaml" />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" loading={loading}>提取并预览</Button>
                  </Form>
                  {remoteMeta.remote_url && (
                    <div className="remote-meta">
                      <div><strong>最近来源：</strong>{remoteMeta.remote_url}</div>
                      <div><strong>最近提取：</strong><DateTime value={remoteMeta.remote_updated_at} /></div>
                    </div>
                  )}
                </div>
              )
            },
            {
              key: "paste",
              label: "粘贴提取",
              children: (
                <div className="settings-pane">
                  <Form form={extractForm} layout="vertical" onFinish={extract}>
                    <Form.Item name="config_text" label="完整 mihomo/Clash 配置" rules={[{ required: true }]}>
                      <TextArea className="monospace-area" rows={20} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit" loading={loading}>提取并预览</Button>
                  </Form>
                </div>
              )
            }
          ]}
        />
      </WorkSurface>
      <Modal
        title={`订阅预览（${preview?.node_count || 0} 个节点）`}
        open={!!preview}
        width={860}
        onCancel={() => setPreview(null)}
        footer={<Button type="primary" onClick={() => setPreview(null)}>完成</Button>}
      >
        <pre className="preview-panel">{preview?.yaml}</pre>
      </Modal>
      <Modal
        title="节点顺序"
        open={orderModalOpen}
        width={620}
        okText="应用"
        cancelText="取消"
        onOk={applyOrderKeywords}
        onCancel={() => setOrderModalOpen(false)}
      >
        <div className="node-order-modal">
          <div className="node-order-add">
            <Input
              value={orderInput}
              placeholder="输入节点名称关键词，如 香港"
              onChange={(event) => setOrderInput(event.target.value)}
              onPressEnter={addOrderKeyword}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={addOrderKeyword}>添加</Button>
          </div>
          <div className="node-order-list" aria-label="节点顺序列表">
            {orderDraft.length ? orderDraft.map((keyword, index) => (
              <div
                key={`${keyword}-${index}`}
                className="node-order-item"
                draggable
                onDragStart={() => setDragIndex(index)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => {
                  moveOrderKeyword(dragIndex, index);
                  setDragIndex(null);
                }}
                onDragEnd={() => setDragIndex(null)}
              >
                <HolderOutlined className="node-order-handle" />
                <span className="node-order-index">{index + 1}</span>
                <span className="node-order-keyword">{keyword}</span>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  aria-label={`删除 ${keyword}`}
                  onClick={() => removeOrderKeyword(index)}
                />
              </div>
            )) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未设置节点顺序" />
            )}
          </div>
        </div>
      </Modal>
    </>
  );
}
