import { Button, Form, Input, Modal, Popconfirm, Select, Space, Switch, Table, Tag, message } from "antd";
import { PlusOutlined, ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { api, applyFormErrors, pageData } from "../api/client";
import { DateTime, EllipsisText, EmptyState, PageHeader, WorkSurface } from "../components/Common";
import useDebouncedValue from "../hooks/useDebouncedValue";


export default function SourcesPage() {
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({ search: "", enabled: "", sync_status: "" });
  const search = useDebouncedValue(filters.search);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [syncingId, setSyncingId] = useState(null);
  const [switchingId, setSwitchingId] = useState(null);
  const [bulkSyncing, setBulkSyncing] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form] = Form.useForm();

  async function load(page = pagination.current, pageSize = pagination.pageSize) {
    setLoading(true);
    try {
      const data = pageData(await api.listSources({
        page,
        page_size: pageSize,
        search,
        enabled: filters.enabled,
        sync_status: filters.sync_status
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
    load(1, pagination.pageSize);
  }, [search, filters.enabled, filters.sync_status]);

  function startCreate() {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ enabled: true });
    setOpen(true);
  }

  function startEdit(row) {
    setEditing(row);
    form.setFieldsValue(row);
    setOpen(true);
  }

  async function submit(values) {
    setSubmitting(true);
    try {
      if (editing) {
        await api.updateSource(editing.id, values);
        message.success("订阅源已更新");
      } else {
        await api.createSource(values);
        message.success("订阅源已创建");
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

  async function updateEnabled(row, enabled) {
    setSwitchingId(row.id);
    try {
      await api.updateSource(row.id, { enabled });
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setSwitchingId(null);
    }
  }

  function syncMessage(result) {
    return `新增 ${result.created}，更新 ${result.updated}，删除 ${result.deleted}，当前 ${result.count} 个节点`;
  }

  async function sync(row) {
    setSyncingId(row.id);
    try {
      const result = await api.syncSource(row.id);
      message.success(syncMessage(result));
    } catch (error) {
      message.error(error.message);
    } finally {
      setSyncingId(null);
      await load();
    }
  }

  async function bulkSync() {
    setBulkSyncing(true);
    try {
      const result = await api.bulkSyncSources(selectedRowKeys);
      if (result.failed) {
        message.warning(`同步完成：成功 ${result.succeeded}，失败 ${result.failed}`);
      } else {
        message.success(`已同步 ${result.succeeded} 个订阅源`);
      }
      setSelectedRowKeys([]);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setBulkSyncing(false);
    }
  }

  async function remove(row) {
    try {
      await api.deleteSource(row.id);
      message.success("订阅源已删除，已有节点保留为无来源节点");
      await load();
    } catch (error) {
      message.error(error.message);
    }
  }

  function clearFilters() {
    setFilters({ search: "", enabled: "", sync_status: "" });
  }

  return (
    <>
      <PageHeader
        title="订阅源"
        description="管理远程 mihomo/Clash 配置及同步状态。"
        meta={<Tag>{pagination.total} 个</Tag>}
        actions={<Button type="primary" icon={<PlusOutlined />} onClick={startCreate}>新增订阅源</Button>}
      />
      <WorkSurface
        toolbar={
          <>
            <Input.Search
              allowClear
              value={filters.search}
              placeholder="搜索名称或 URL"
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
            <Select
              value={filters.sync_status}
              style={{ width: 140 }}
              options={[
                { value: "", label: "全部同步状态" },
                { value: "success", label: "同步正常" },
                { value: "error", label: "同步异常" },
                { value: "never", label: "从未同步" }
              ]}
              onChange={(sync_status) => setFilters({ ...filters, sync_status })}
            />
            <Button icon={<ReloadOutlined />} onClick={clearFilters}>清除筛选</Button>
            <span className="filter-spacer" />
            {selectedRowKeys.length > 0 && <span className="selection-count">已选 {selectedRowKeys.length} 项</span>}
            <Button
              icon={<SyncOutlined />}
              loading={bulkSyncing}
              disabled={!selectedRowKeys.length}
              onClick={bulkSync}
            >
              批量同步
            </Button>
          </>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          rowSelection={{ selectedRowKeys, preserveSelectedRowKeys: true, onChange: setSelectedRowKeys }}
          dataSource={items}
          scroll={{ x: 1050 }}
          pagination={{ ...pagination, showSizeChanger: true, showTotal: (total) => `共 ${total} 条` }}
          onChange={(next) => load(next.current, next.pageSize)}
          locale={{
            emptyText: (
              <EmptyState
                title={filters.search || filters.enabled || filters.sync_status ? "没有匹配的订阅源" : "还没有订阅源"}
                description={filters.search || filters.enabled || filters.sync_status ? "请调整筛选条件。" : "添加远程订阅地址后即可同步节点。"}
                actions={filters.search || filters.enabled || filters.sync_status
                  ? <Button onClick={clearFilters}>清除筛选</Button>
                  : <Button type="primary" onClick={startCreate}>新增订阅源</Button>}
              />
            )
          }}
          columns={[
            { title: "名称", dataIndex: "name", width: 180, fixed: "left", render: (value) => <EllipsisText width={165}>{value}</EllipsisText> },
            { title: "URL", dataIndex: "url", width: 280, render: (value) => <EllipsisText width={260}>{value}</EllipsisText> },
            { title: "节点", dataIndex: "node_count", width: 75 },
            {
              title: "同步状态",
              width: 110,
              render: (_, row) => row.last_error
                ? <Tag color="error">异常</Tag>
                : row.last_synced_at ? <Tag color="success">正常</Tag> : <Tag>未同步</Tag>
            },
            { title: "最近同步", dataIndex: "last_synced_at", width: 180, render: (value) => <DateTime value={value} /> },
            { title: "错误", dataIndex: "last_error", width: 200, render: (value) => <EllipsisText width={185}>{value}</EllipsisText> },
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
              width: 210,
              fixed: "right",
              render: (_, row) => (
                <Space>
                  <Button onClick={() => startEdit(row)}>编辑</Button>
                  <Button loading={syncingId === row.id} icon={<SyncOutlined />} onClick={() => sync(row)}>同步</Button>
                  <Popconfirm
                    title="删除订阅源？"
                    description={`该订阅源关联 ${row.node_count} 个节点。删除后节点会保留，但不再参与远程同步。`}
                    onConfirm={() => remove(row)}
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
        title={editing ? "编辑订阅源" : "新增订阅源"}
        open={open}
        confirmLoading={submitting}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="订阅 URL" rules={[{ required: true }, { type: "url", message: "请输入有效 URL" }]}>
            <Input />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
