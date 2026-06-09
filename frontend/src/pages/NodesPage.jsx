import {
  Alert,
  Button,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  message
} from "antd";
import { CheckOutlined, DeleteOutlined, PlusOutlined, ReloadOutlined, StopOutlined } from "@ant-design/icons";
import yaml from "js-yaml";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, pageData } from "../api/client";
import { EllipsisText, EmptyState, PageHeader, WorkSurface } from "../components/Common";
import YamlEditor from "../components/YamlEditor";
import useDebouncedValue from "../hooks/useDebouncedValue";

const { TextArea } = Input;


export default function NodesPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [options, setOptions] = useState({ types: [], sources: [] });
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({ search: "", source: "", type: "", enabled: "" });
  const search = useDebouncedValue(filters.search);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [switchingId, setSwitchingId] = useState(null);
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editorYaml, setEditorYaml] = useState("");
  const [yamlError, setYamlError] = useState("");
  const [form] = Form.useForm();
  const [editForm] = Form.useForm();

  async function load(page = pagination.current, pageSize = pagination.pageSize) {
    setLoading(true);
    try {
      const data = pageData(await api.listNodes({
        page,
        page_size: pageSize,
        search,
        source: filters.source,
        type: filters.type,
        enabled: filters.enabled
      }));
      const current = data.items.length === 0 && page > 1 ? page - 1 : page;
      if (current !== page) {
        return load(current, pageSize);
      }
      setItems(data.items);
      setPagination({ current, pageSize, total: data.count });
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.nodeOptions().then(setOptions).catch((error) => message.error(error.message));
  }, []);

  useEffect(() => {
    load(1, pagination.pageSize);
  }, [search, filters.source, filters.type, filters.enabled]);

  function clearFilters() {
    setFilters({ search: "", source: "", type: "", enabled: "" });
  }

  function openCreate() {
    form.resetFields();
    setPreview(null);
    setOpen(true);
  }

  async function previewNode() {
    try {
      const values = await form.validateFields();
      setPreviewing(true);
      const result = await api.previewNode(values.node_text);
      setPreview(result.config);
    } catch (error) {
      if (error?.errorFields) {
        return;
      }
      message.error(error.message);
    } finally {
      setPreviewing(false);
    }
  }

  async function create() {
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      await api.createManualNode(values.node_text);
      message.success("节点已添加");
      setOpen(false);
      await load(1);
      setOptions(await api.nodeOptions());
    } catch (error) {
      message.error(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(row) {
    setEditing(row);
    setYamlError("");
    setEditorYaml(yaml.dump(row.config || {}, { lineWidth: -1 }));
    editForm.setFieldsValue({
      name: row.config?.name || row.name,
      type: row.config?.type || row.type,
      server: row.config?.server,
      port: row.config?.port,
      tags: row.tags || "",
      remark: row.remark || "",
      enabled: row.enabled
    });
  }

  function validateYaml(value) {
    setEditorYaml(value);
    try {
      const parsed = yaml.load(value);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("节点 YAML 顶层必须是对象");
      }
      setYamlError("");
    } catch (error) {
      setYamlError(error.mark ? `第 ${error.mark.line + 1} 行，第 ${error.mark.column + 1} 列：${error.reason}` : error.message);
    }
  }

  async function saveEdit() {
    let config;
    try {
      config = yaml.load(editorYaml);
      if (!config || typeof config !== "object" || Array.isArray(config)) {
        throw new Error("节点 YAML 顶层必须是对象");
      }
    } catch (error) {
      validateYaml(editorYaml);
      return;
    }
    try {
      const values = await editForm.validateFields();
      config = {
        ...config,
        name: values.name,
        type: values.type,
        server: values.server || undefined,
        port: values.port || undefined
      };
      setSubmitting(true);
      await api.updateNode(editing.id, {
        tags: values.tags || "",
        remark: values.remark || "",
        enabled: values.enabled,
        config
      });
      message.success("节点已更新");
      setEditing(null);
      await load();
      setOptions(await api.nodeOptions());
    } catch (error) {
      if (!error?.errorFields) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function bulkState(enabled) {
    setLoading(true);
    try {
      const result = await api.bulkSetNodeState(selectedRowKeys, enabled);
      message.success(`已${enabled ? "启用" : "禁用"} ${result.updated} 个节点`);
      setSelectedRowKeys([]);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function bulkDelete() {
    setLoading(true);
    try {
      await api.bulkDeleteNodes(selectedRowKeys);
      message.success("已删除所选节点");
      setSelectedRowKeys([]);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function toggle(row) {
    setSwitchingId(row.id);
    try {
      await api.toggleNode(row.id);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setSwitchingId(null);
    }
  }

  async function remove(id) {
    try {
      await api.deleteNode(id);
      message.success("节点已删除");
      await load();
    } catch (error) {
      message.error(error.message);
    }
  }

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <>
      <PageHeader
        title="节点"
        description="筛选、启停和编辑订阅节点。"
        meta={<Tag>{pagination.total} 个结果</Tag>}
        actions={<Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>手动添加</Button>}
      />
      <WorkSurface
        toolbar={
          <>
            <Input.Search
              allowClear
              value={filters.search}
              placeholder="搜索名称、标签或备注"
              style={{ width: 260 }}
              onChange={(event) => setFilters({ ...filters, search: event.target.value })}
            />
            <Select
              value={filters.source}
              style={{ width: 150 }}
              options={[
                { value: "", label: "全部来源" },
                { value: "manual", label: "手动添加" },
                ...options.sources.map((source) => ({ value: String(source.id), label: source.name }))
              ]}
              onChange={(source) => setFilters({ ...filters, source })}
            />
            <Select
              value={filters.type}
              style={{ width: 130 }}
              options={[{ value: "", label: "全部协议" }, ...options.types.map((type) => ({ value: type, label: type }))]}
              onChange={(type) => setFilters({ ...filters, type })}
            />
            <Select
              value={filters.enabled}
              style={{ width: 130 }}
              options={[
                { value: "", label: "全部状态" },
                { value: "true", label: "已启用" },
                { value: "false", label: "已禁用" }
              ]}
              onChange={(enabled) => setFilters({ ...filters, enabled })}
            />
            <Button icon={<ReloadOutlined />} onClick={clearFilters}>清除筛选</Button>
            <span className="filter-spacer" />
            {selectedRowKeys.length > 0 && <span className="selection-count">已选 {selectedRowKeys.length} 个</span>}
            <Button icon={<CheckOutlined />} disabled={!selectedRowKeys.length} onClick={() => bulkState(true)}>启用</Button>
            <Button icon={<StopOutlined />} disabled={!selectedRowKeys.length} onClick={() => bulkState(false)}>禁用</Button>
            <Popconfirm title={`删除选中的 ${selectedRowKeys.length} 个节点？`} onConfirm={bulkDelete}>
              <Button danger icon={<DeleteOutlined />} disabled={!selectedRowKeys.length}>删除</Button>
            </Popconfirm>
          </>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          rowSelection={{ selectedRowKeys, preserveSelectedRowKeys: true, onChange: setSelectedRowKeys }}
          dataSource={items}
          scroll={{ x: 950 }}
          pagination={{ ...pagination, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          onChange={(next) => load(next.current, next.pageSize)}
          locale={{
            emptyText: (
              <EmptyState
                title={hasFilters ? "没有匹配的节点" : "还没有节点"}
                description={hasFilters ? "请调整筛选条件。" : "同步订阅源或手动添加第一个节点。"}
                actions={hasFilters
                  ? <Button onClick={clearFilters}>清除筛选</Button>
                  : <>
                    <Button onClick={() => navigate("/sources")}>同步订阅源</Button>
                    <Button type="primary" onClick={openCreate}>手动添加</Button>
                  </>}
              />
            )
          }}
          columns={[
            { title: "名称", dataIndex: "name", width: 220, fixed: "left", render: (value) => <EllipsisText width={205}>{value}</EllipsisText> },
            { title: "协议", dataIndex: "type", width: 100, render: (value) => <Tag>{value}</Tag> },
            { title: "来源", dataIndex: "source_label", width: 170, render: (value) => <EllipsisText width={155}>{value}</EllipsisText> },
            { title: "标签", dataIndex: "tags", width: 160, responsive: ["md"], render: (value) => <EllipsisText width={145}>{value}</EllipsisText> },
            { title: "备注", dataIndex: "remark", width: 180, responsive: ["lg"], render: (value) => <EllipsisText width={165}>{value}</EllipsisText> },
            {
              title: "启用",
              dataIndex: "enabled",
              width: 80,
              render: (_, row) => (
                <Switch
                  size="small"
                  checked={row.enabled}
                  loading={switchingId === row.id}
                  disabled={switchingId === row.id}
                  onChange={() => toggle(row)}
                />
              )
            },
            {
              title: "操作",
              width: 150,
              fixed: "right",
              render: (_, row) => (
                <Space>
                  <Button onClick={() => startEdit(row)}>编辑</Button>
                  <Popconfirm title="删除节点？" description="用户与该节点的绑定也会被解除。" onConfirm={() => remove(row.id)}>
                    <Button danger>删除</Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
        />
      </WorkSurface>

      <Modal
        title="手动添加节点"
        open={open}
        width={760}
        confirmLoading={submitting}
        okText={preview ? "确认添加" : "请先解析"}
        okButtonProps={{ disabled: !preview }}
        onCancel={() => setOpen(false)}
        onOk={create}
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            <CancelBtn />
            <Button loading={previewing} onClick={previewNode}>解析预览</Button>
            <OkBtn />
          </>
        )}
      >
        <Form form={form} layout="vertical" onValuesChange={() => setPreview(null)}>
          <Form.Item name="node_text" label="URI 或 YAML 节点配置" rules={[{ required: true, message: "请输入节点配置" }]}>
            <TextArea className="monospace-area" rows={10} />
          </Form.Item>
        </Form>
        {preview && (
          <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
            <Descriptions.Item label="名称">{preview.name}</Descriptions.Item>
            <Descriptions.Item label="协议">{preview.type}</Descriptions.Item>
            <Descriptions.Item label="服务器">{preview.server || "无"}</Descriptions.Item>
            <Descriptions.Item label="端口">{preview.port || "无"}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal
        title="编辑节点"
        open={!!editing}
        width={820}
        confirmLoading={submitting}
        onCancel={() => setEditing(null)}
        onOk={saveEdit}
      >
        <Tabs
          items={[
            {
              key: "basic",
              label: "基础配置",
              children: (
                <Form form={editForm} layout="vertical">
                  <div className="form-grid">
                    <Form.Item name="name" label="名称" rules={[{ required: true }]}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="type" label="协议" rules={[{ required: true }]}>
                      <Input />
                    </Form.Item>
                    <Form.Item name="server" label="服务器">
                      <Input />
                    </Form.Item>
                    <Form.Item name="port" label="端口">
                      <InputNumber min={1} max={65535} style={{ width: "100%" }} />
                    </Form.Item>
                  </div>
                  <Form.Item name="tags" label="标签">
                    <Input placeholder="例如：香港, 高速" />
                  </Form.Item>
                  <Form.Item name="remark" label="备注">
                    <Input />
                  </Form.Item>
                  <Form.Item name="enabled" label="启用" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                </Form>
              )
            },
            {
              key: "yaml",
              label: "高级 YAML",
              children: (
                <>
                  {yamlError && <Alert type="error" showIcon message={yamlError} style={{ marginBottom: 12 }} />}
                  <YamlEditor value={editorYaml} onChange={validateYaml} minHeight="360px" />
                </>
              )
            }
          ]}
        />
      </Modal>
    </>
  );
}
