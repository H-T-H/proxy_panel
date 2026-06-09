import {
  Button,
  Checkbox,
  Collapse,
  Form,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message
} from "antd";
import {
  ClearOutlined,
  CopyOutlined,
  PlusOutlined,
  ReloadOutlined
} from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";

import { api, applyFormErrors, pageData } from "../api/client";
import { CopyButton, EllipsisText, EmptyState, PageHeader, WorkSurface } from "../components/Common";
import useDebouncedValue from "../hooks/useDebouncedValue";

const { Text } = Typography;


function fullSubscriptionUrl(path) {
  return new URL(path, window.location.origin).toString();
}


export default function UsersPage() {
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({ search: "", enabled: "" });
  const search = useDebouncedValue(filters.search);
  const [nodeOptions, setNodeOptions] = useState({ types: [], sources: [] });
  const [nodes, setNodes] = useState([]);
  const [nodePagination, setNodePagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [nodeFilters, setNodeFilters] = useState({ search: "", source: "", type: "", enabled: "" });
  const nodeSearch = useDebouncedValue(nodeFilters.search);
  const [selectedNodeIds, setSelectedNodeIds] = useState([]);
  const [bindingMode, setBindingMode] = useState("列表");
  const [loading, setLoading] = useState(false);
  const [nodeLoading, setNodeLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [switchingId, setSwitchingId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);
  const [resetResult, setResetResult] = useState(null);
  const [form] = Form.useForm();

  async function load(page = pagination.current, pageSize = pagination.pageSize) {
    setLoading(true);
    try {
      const data = pageData(await api.listUsers({
        page,
        page_size: pageSize,
        search,
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

  async function loadNodes(page = nodePagination.current, pageSize = nodePagination.pageSize) {
    setNodeLoading(true);
    try {
      const data = pageData(await api.listNodes({
        page,
        page_size: pageSize,
        search: nodeSearch,
        source: nodeFilters.source,
        type: nodeFilters.type,
        enabled: nodeFilters.enabled
      }));
      setNodes(data.items);
      setNodePagination({ current: page, pageSize, total: data.count });
    } catch (error) {
      message.error(error.message);
    } finally {
      setNodeLoading(false);
    }
  }

  useEffect(() => {
    load(1, pagination.pageSize);
  }, [search, filters.enabled]);

  useEffect(() => {
    if (open) {
      loadNodes(1, nodePagination.pageSize);
    }
  }, [nodeSearch, nodeFilters.source, nodeFilters.type, nodeFilters.enabled]);

  async function openEditor(row = null) {
    setEditing(row);
    setSelectedNodeIds(row?.node_ids || []);
    setNodeFilters({ search: "", source: "", type: "", enabled: "" });
    setBindingMode("列表");
    form.resetFields();
    form.setFieldsValue(row ? { ...row } : { enabled: true });
    setOpen(true);
    try {
      const options = await api.nodeOptions();
      setNodeOptions(options);
      await loadNodes(1, 10);
    } catch (error) {
      message.error(error.message);
    }
  }

  async function submit(values) {
    setSubmitting(true);
    try {
      const payload = { ...values, node_ids: selectedNodeIds };
      if (editing) {
        await api.updateUser(editing.id, payload);
        message.success("用户已更新");
      } else {
        await api.createUser(payload);
        message.success("用户已创建");
      }
      setOpen(false);
      await load(editing ? pagination.current : 1, pagination.pageSize);
    } catch (error) {
      if (!applyFormErrors(form, error)) {
        message.error(error.message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function selectAllFiltered() {
    setNodeLoading(true);
    try {
      const ids = [];
      let page = 1;
      let count = 0;
      do {
        const result = pageData(await api.listNodes({
          page,
          page_size: 100,
          search: nodeSearch,
          source: nodeFilters.source,
          type: nodeFilters.type,
          enabled: nodeFilters.enabled
        }));
        ids.push(...result.items.map((node) => node.id));
        count = result.count;
        page += 1;
      } while (ids.length < count);
      setSelectedNodeIds(Array.from(new Set([...selectedNodeIds, ...ids])));
      message.success(`已选择当前筛选结果中的 ${ids.length} 个节点`);
    } catch (error) {
      message.error(error.message);
    } finally {
      setNodeLoading(false);
    }
  }

  async function updateEnabled(row, enabled) {
    setSwitchingId(row.id);
    try {
      await api.updateUser(row.id, { enabled });
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setSwitchingId(null);
    }
  }

  async function resetToken(row) {
    try {
      const result = await api.resetUserToken(row.id);
      setResetResult({ username: result.username, url: fullSubscriptionUrl(result.subscription_path) });
      await load();
    } catch (error) {
      message.error(error.message);
    }
  }

  async function remove(id) {
    try {
      await api.deleteUser(id);
      message.success("用户已删除，原订阅地址已失效");
      await load();
    } catch (error) {
      message.error(error.message);
    }
  }

  const groupedNodes = useMemo(() => {
    const groups = new Map();
    nodes.forEach((node) => {
      const label = node.source_label || "其他";
      if (!groups.has(label)) {
        groups.set(label, []);
      }
      groups.get(label).push(node);
    });
    return Array.from(groups.entries());
  }, [nodes]);

  const hasFilters = filters.search || filters.enabled;

  return (
    <>
      <PageHeader
        title="用户"
        description="管理订阅用户、节点授权和订阅地址。"
        meta={<Tag>{pagination.total} 个</Tag>}
        actions={<Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor()}>创建用户</Button>}
      />
      <WorkSurface
        toolbar={
          <>
            <Input.Search
              allowClear
              value={filters.search}
              placeholder="搜索用户名或备注"
              style={{ width: 260 }}
              onChange={(event) => setFilters({ ...filters, search: event.target.value })}
            />
            <Select
              value={filters.enabled}
              style={{ width: 130 }}
              options={[
                { value: "", label: "全部状态" },
                { value: "true", label: "已启用" },
                { value: "false", label: "已停用" }
              ]}
              onChange={(enabled) => setFilters({ ...filters, enabled })}
            />
            <Button icon={<ReloadOutlined />} onClick={() => setFilters({ search: "", enabled: "" })}>清除筛选</Button>
          </>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          scroll={{ x: 1050 }}
          pagination={{ ...pagination, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          onChange={(next) => load(next.current, next.pageSize)}
          locale={{
            emptyText: (
              <EmptyState
                title={hasFilters ? "没有匹配的用户" : "还没有订阅用户"}
                description={hasFilters ? "请调整筛选条件。" : "创建用户并分配节点后即可生成订阅地址。"}
                actions={hasFilters
                  ? <Button onClick={() => setFilters({ search: "", enabled: "" })}>清除筛选</Button>
                  : <Button type="primary" onClick={() => openEditor()}>创建用户</Button>}
              />
            )
          }}
          columns={[
            { title: "用户名", dataIndex: "username", width: 160, fixed: "left" },
            { title: "备注", dataIndex: "remark", width: 160, responsive: ["md"], render: (value) => <EllipsisText width={145}>{value}</EllipsisText> },
            { title: "节点", dataIndex: "node_count", width: 70 },
            {
              title: "订阅地址",
              dataIndex: "subscription_path",
              width: 360,
              render: (path) => {
                const url = fullSubscriptionUrl(path);
                return (
                  <div className="subscription-cell">
                    <EllipsisText width={245}>{url}</EllipsisText>
                    <CopyButton text={url} />
                  </div>
                );
              }
            },
            {
              title: "启用",
              dataIndex: "enabled",
              width: 80,
              render: (value, row) => (
                <Switch
                  size="small"
                  checked={value}
                  loading={switchingId === row.id}
                  disabled={switchingId === row.id}
                  onChange={(enabled) => updateEnabled(row, enabled)}
                />
              )
            },
            {
              title: "操作",
              width: 260,
              fixed: "right",
              render: (_, row) => (
                <Space>
                  <Button onClick={() => openEditor(row)}>编辑</Button>
                  <Popconfirm
                    title="重置订阅 Token？"
                    description="旧订阅地址将立即失效，客户端需要更新为新地址。"
                    onConfirm={() => resetToken(row)}
                  >
                    <Button>重置 Token</Button>
                  </Popconfirm>
                  <Popconfirm
                    title="删除用户？"
                    description="该用户的订阅地址将立即失效。"
                    onConfirm={() => remove(row.id)}
                  >
                    <Button danger>删除</Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
        />
      </WorkSurface>

      <Modal
        title={editing ? "编辑用户" : "创建用户"}
        open={open}
        confirmLoading={submitting}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        width={900}
      >
        <Form form={form} layout="vertical" onFinish={submit}>
          <div className="form-grid">
            <Form.Item name="username" label="用户名" rules={[{ required: true, message: "请输入用户名" }]}>
              <Input />
            </Form.Item>
            <Form.Item name="remark" label="备注">
              <Input />
            </Form.Item>
            <Form.Item
              name="password"
              label={editing ? "重置登录密码" : "初始登录密码"}
              extra={editing ? "留空表示不修改登录密码；此操作不会重置订阅 Token。" : null}
              rules={editing ? [] : [{ required: true, message: "请设置初始登录密码" }]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
          </div>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label={`绑定节点（已选 ${selectedNodeIds.length}）`}>
            <div className="binding-toolbar">
              <Input.Search
                allowClear
                placeholder="搜索节点"
                value={nodeFilters.search}
                onChange={(event) => setNodeFilters({ ...nodeFilters, search: event.target.value })}
              />
              <Select
                value={nodeFilters.source}
                options={[
                  { value: "", label: "全部来源" },
                  { value: "manual", label: "手动添加" },
                  ...nodeOptions.sources.map((source) => ({ value: String(source.id), label: source.name }))
                ]}
                onChange={(source) => setNodeFilters({ ...nodeFilters, source })}
              />
              <Select
                value={nodeFilters.type}
                options={[{ value: "", label: "全部协议" }, ...nodeOptions.types.map((type) => ({ value: type, label: type }))]}
                onChange={(type) => setNodeFilters({ ...nodeFilters, type })}
              />
              <Select
                value={nodeFilters.enabled}
                options={[
                  { value: "", label: "全部状态" },
                  { value: "true", label: "已启用" },
                  { value: "false", label: "已禁用" }
                ]}
                onChange={(enabled) => setNodeFilters({ ...nodeFilters, enabled })}
              />
            </div>
            <div className="binding-actions">
              <Segmented options={["列表", "按来源分组"]} value={bindingMode} onChange={setBindingMode} />
              <Space>
                <Button onClick={selectAllFiltered}>全选当前筛选结果</Button>
                <Button icon={<ClearOutlined />} disabled={!selectedNodeIds.length} onClick={() => setSelectedNodeIds([])}>清空绑定</Button>
              </Space>
            </div>
            {bindingMode === "列表" ? (
              <Table
                className="modal-table"
                size="small"
                rowKey="id"
                loading={nodeLoading}
                dataSource={nodes}
                rowSelection={{
                  selectedRowKeys: selectedNodeIds,
                  preserveSelectedRowKeys: true,
                  onChange: setSelectedNodeIds
                }}
                scroll={{ x: 620 }}
                pagination={{
                  ...nodePagination,
                  showSizeChanger: true,
                  pageSizeOptions: [10, 20, 50, 100],
                  showTotal: (total) => `共 ${total} 个节点`
                }}
                onChange={(next) => loadNodes(next.current, next.pageSize)}
                columns={[
                  { title: "名称", dataIndex: "name", render: (value) => <EllipsisText width={260}>{value}</EllipsisText> },
                  { title: "协议", dataIndex: "type", width: 100 },
                  { title: "来源", dataIndex: "source_label", width: 180 }
                ]}
              />
            ) : (
              <Collapse
                className="grouped-nodes"
                items={groupedNodes.map(([source, sourceNodes]) => ({
                  key: source,
                  label: `${source}（${sourceNodes.length}）`,
                  children: (
                    <Checkbox.Group
                      value={selectedNodeIds}
                      onChange={(currentIds) => {
                        const visibleIds = new Set(nodes.map((node) => node.id));
                        setSelectedNodeIds([
                          ...selectedNodeIds.filter((id) => !visibleIds.has(id)),
                          ...currentIds
                        ]);
                      }}
                      className="node-checkbox-grid"
                    >
                      {sourceNodes.map((node) => (
                        <Checkbox key={node.id} value={node.id}>
                          {node.name} <Text type="secondary">({node.type})</Text>
                        </Checkbox>
                      ))}
                    </Checkbox.Group>
                  )
                }))}
              />
            )}
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Token 已重置"
        open={!!resetResult}
        onCancel={() => setResetResult(null)}
        footer={<Button type="primary" onClick={() => setResetResult(null)}>完成</Button>}
      >
        <p><strong>{resetResult?.username}</strong> 的旧订阅地址已经失效，请将新地址更新到客户端。</p>
        <Space.Compact block>
          <Input readOnly value={resetResult?.url} />
          <Button
            aria-label="复制新订阅地址"
            icon={<CopyOutlined />}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(resetResult.url);
                message.success("新订阅地址已复制");
              } catch {
                message.error("复制失败，请手动复制");
              }
            }}
          />
        </Space.Compact>
      </Modal>
    </>
  );
}
