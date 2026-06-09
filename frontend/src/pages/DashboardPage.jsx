import { Alert, Button, Skeleton, Space, Table, Tag, message } from "antd";
import { PlusOutlined, SyncOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";
import { DateTime, EllipsisText, EmptyState, PageHeader, WorkSurface } from "../components/Common";


export default function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [syncing, setSyncing] = useState(null);

  async function load() {
    try {
      setData(await api.dashboard());
    } catch (error) {
      message.error(error.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function syncSource(source) {
    setSyncing(source.id);
    try {
      const result = await api.syncSource(source.id);
      message.success(`同步完成：新增 ${result.created}，更新 ${result.updated}，删除 ${result.deleted}`);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setSyncing(null);
    }
  }

  if (!data) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  const stats = [
    { label: "订阅源", value: data.sources },
    { label: "节点", value: data.nodes },
    { label: "用户", value: data.users },
    { label: "异常", value: data.source_errors }
  ];

  return (
    <>
      <PageHeader
        title="仪表盘"
        description="订阅服务概览。"
        actions={[
          <Button key="source" type="primary" icon={<PlusOutlined />} onClick={() => navigate("/sources")}>新增订阅源</Button>,
          <Button key="user" onClick={() => navigate("/users")}>创建用户</Button>
        ]}
      />
      {data.source_errors > 0 && (
        <Alert
          showIcon
          type="error"
          className="dashboard-alert"
          message={`${data.source_errors} 个订阅源同步异常`}
          description="请检查最近订阅源列表中的错误信息，并重新同步。"
          action={<Button size="small" onClick={() => navigate("/sources")}>查看订阅源</Button>}
        />
      )}
      <div className="stats-grid">
        {stats.map((item) => (
          <div className="stat-panel" key={item.label}>
            <div className="stat-label">{item.label}</div>
            <div className="stat-primary">{item.value}</div>
          </div>
        ))}
      </div>
      <WorkSurface
        toolbar={
          <>
            <strong>最近同步</strong>
            <span className="stat-secondary">最后成功同步：<DateTime value={data.latest_synced_at} /></span>
            <span className="filter-spacer" />
            <Button onClick={() => navigate("/sources")}>管理全部</Button>
          </>
        }
      >
        <Table
          rowKey="id"
          dataSource={data.recent_sources}
          pagination={false}
          scroll={{ x: 760 }}
          locale={{
            emptyText: (
              <EmptyState
                title="还没有订阅源"
                description="添加订阅源并同步后，节点会出现在这里。"
                actions={<Button type="primary" onClick={() => navigate("/sources")}>新增订阅源</Button>}
              />
            )
          }}
          columns={[
            { title: "名称", dataIndex: "name", width: 180, render: (value) => <EllipsisText width={170}>{value}</EllipsisText> },
            { title: "节点", dataIndex: "node_count", width: 80 },
            {
              title: "状态",
              width: 100,
              render: (_, row) => row.last_error
                ? <Tag color="error">异常</Tag>
                : row.last_synced_at ? <Tag color="success">正常</Tag> : <Tag>未同步</Tag>
            },
            { title: "最近同步", dataIndex: "last_synced_at", width: 180, render: (value) => <DateTime value={value} /> },
            { title: "错误", dataIndex: "last_error", render: (value) => <EllipsisText width={260}>{value}</EllipsisText> },
            {
              title: "操作",
              width: 100,
              fixed: "right",
              render: (_, row) => (
                <Button
                  icon={<SyncOutlined />}
                  loading={syncing === row.id}
                  onClick={() => syncSource(row)}
                >
                  同步
                </Button>
              )
            }
          ]}
        />
      </WorkSurface>
    </>
  );
}
