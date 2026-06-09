import { Button, Input, Popconfirm, Select, Space, Switch, Table, Tag, Upload, message } from "antd";
import { LinkOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { api, pageData } from "../api/client";
import { EllipsisText, EmptyState, PageHeader, WorkSurface } from "../components/Common";
import useDebouncedValue from "../hooks/useDebouncedValue";

const PLATFORM_OPTIONS = [
  { value: "", label: "全部平台" },
  { value: "ios", label: "iOS" },
  { value: "mac", label: "macOS" },
  { value: "windows", label: "Windows" },
  { value: "linux", label: "Linux" },
  { value: "android", label: "Android" }
];

function platformLabel(value) {
  return PLATFORM_OPTIONS.find((item) => item.value === value)?.label || value;
}

function ClientIcon({ item }) {
  if (!item.icon_url) {
    return <span className="client-icon-fallback">{item.name?.slice(0, 1) || "C"}</span>;
  }
  return <img className="client-icon" src={item.icon_url} alt="" loading="lazy" referrerPolicy="no-referrer" />;
}

export default function ClientsPage() {
  const [items, setItems] = useState([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({ search: "", enabled: "", platform_code: "" });
  const search = useDebouncedValue(filters.search);
  const [portalEnabled, setPortalEnabled] = useState(false);
  const [platforms, setPlatforms] = useState(PLATFORM_OPTIONS.filter((item) => item.value).map((item) => ({
    key: item.value,
    label: item.label,
    enabled: true
  })));
  const [loading, setLoading] = useState(false);

  async function load(page = pagination.current, pageSize = pagination.pageSize) {
    setLoading(true);
    try {
      const [config, payload] = await Promise.all([
        api.getClientDownloadConfig(),
        api.listClientDownloads({
          page,
          page_size: pageSize,
          search,
          enabled: filters.enabled,
          platform_code: filters.platform_code
        })
      ]);
      const data = pageData(payload);
      const current = data.items.length === 0 && page > 1 ? page - 1 : page;
      if (current !== page) {
        return load(current, pageSize);
      }
      setPortalEnabled(!!config.enabled);
      setPlatforms(config.platforms || platforms);
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
  }, [search, filters.enabled, filters.platform_code]);

  async function togglePortal(enabled) {
    setLoading(true);
    try {
      const result = await api.saveClientDownloadConfig(enabled);
      setPortalEnabled(result.enabled);
      message.success(result.enabled ? "已开启用户页客户端入口" : "已关闭用户页客户端入口");
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function togglePlatform(key, enabled) {
    setLoading(true);
    try {
      const result = await api.saveClientDownloadConfig(portalEnabled, { [key]: enabled });
      setPlatforms(result.platforms || platforms);
      message.success("平台展示设置已更新");
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function updateClient(row, patch) {
    setLoading(true);
    try {
      await api.updateClientDownload(row.id, patch);
      await load();
    } catch (error) {
      message.error(error.message);
      await load();
    } finally {
      setLoading(false);
    }
  }

  async function uploadClientFile(row, file) {
    setLoading(true);
    try {
      const payload = new FormData();
      payload.append("upload_file", file);
      await api.updateClientDownload(row.id, payload);
      message.success(`${row.name} 文件已上传`);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function clearClientFile(row) {
    setLoading(true);
    try {
      await api.updateClientDownload(row.id, { clear_file: true });
      message.success(`${row.name} 已恢复为链接`);
      await load();
    } catch (error) {
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }

  const hasFilters = filters.search || filters.enabled || filters.platform_code;

  return (
    <>
      <PageHeader
        title="客户端"
        description="选择要提供给普通用户的内置代理客户端；默认提供官方链接，也可以手动上传本地文件。"
        meta={<>{portalEnabled ? <Tag color="success">用户页已显示</Tag> : <Tag>用户页未显示</Tag>}<Tag>{pagination.total} 个</Tag></>}
        actions={[
          <Button key="refresh" icon={<ReloadOutlined />} onClick={() => load()}>刷新</Button>
        ]}
      />

      <div className="client-control-bar">
        <div className="client-switch-line">
          <span>用户页入口</span>
          <Switch checked={portalEnabled} loading={loading} onChange={togglePortal} />
        </div>
        <div className="client-platform-switches">
          {platforms.map((platform) => (
            <label key={platform.key}>
              <span>{platform.label}</span>
              <Switch
                size="small"
                checked={platform.enabled}
                loading={loading}
                onChange={(enabled) => togglePlatform(platform.key, enabled)}
              />
            </label>
          ))}
        </div>
      </div>

      <WorkSurface
        toolbar={
          <>
            <Input.Search
              allowClear
              value={filters.search}
              placeholder="搜索客户端、平台或地址"
              style={{ width: 300 }}
              onChange={(event) => setFilters({ ...filters, search: event.target.value })}
            />
            <Select
              value={filters.platform_code}
              style={{ width: 130 }}
              options={PLATFORM_OPTIONS}
              onChange={(platform_code) => setFilters({ ...filters, platform_code })}
            />
            <Select
              value={filters.enabled}
              style={{ width: 130 }}
              options={[
                { value: "", label: "全部状态" },
                { value: "true", label: "已提供" },
                { value: "false", label: "未提供" }
              ]}
              onChange={(enabled) => setFilters({ ...filters, enabled })}
            />
            <Button icon={<ReloadOutlined />} onClick={() => setFilters({ search: "", enabled: "", platform_code: "" })}>清除筛选</Button>
          </>
        }
      >
        <Table
          rowKey="id"
          loading={loading}
          dataSource={items}
          scroll={{ x: 1020 }}
          locale={{
            emptyText: (
              <EmptyState
                title={hasFilters ? "没有符合条件的客户端" : "没有内置客户端"}
                description={hasFilters ? "调整筛选条件后再试。" : "请检查后端内置客户端目录。"}
              />
            )
          }}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true
          }}
          onChange={(next) => load(next.current, next.pageSize)}
          columns={[
            {
              title: "客户端",
              dataIndex: "name",
              width: 210,
              fixed: "left",
              render: (value, row) => (
                <div className="client-download-title">
                  <ClientIcon item={row} />
                  <div className="client-download-name">
                    <strong>{value}</strong>
                    {row.remark && <span>{row.remark}</span>}
                  </div>
                </div>
              )
            },
            {
              title: "平台",
              dataIndex: "platform_code",
              width: 105,
              render: (value) => platformLabel(value)
            },
            {
              title: "提供给用户",
              dataIndex: "enabled",
              width: 110,
              render: (value, row) => (
                <Switch checked={value} onChange={(enabled) => updateClient(row, { enabled })} />
              )
            },
            {
              title: "当前",
              width: 110,
              render: (_, row) => row.has_local_file ? <Tag color="processing">本地文件</Tag> : <Tag icon={<LinkOutlined />}>链接</Tag>
            },
            {
              title: "地址 / 文件",
              dataIndex: "download_url",
              width: 320,
              render: (value, row) => (
                <EllipsisText width={300}>
                  {row.has_local_file ? row.file_name : value}
                </EllipsisText>
              )
            },
            {
              title: "操作",
              width: 190,
              fixed: "right",
              render: (_, row) => (
                <Space>
                  <Upload
                    maxCount={1}
                    showUploadList={false}
                    beforeUpload={(file) => {
                      uploadClientFile(row, file);
                      return false;
                    }}
                  >
                    <Button
                      aria-label="上传客户端文件"
                      icon={<UploadOutlined />}
                      disabled={!row.file_available}
                    >
                      上传文件
                    </Button>
                  </Upload>
                  {row.has_local_file && (
                    <Popconfirm
                      title="恢复为官方链接？"
                      okText="恢复"
                      cancelText="取消"
                      onConfirm={() => clearClientFile(row)}
                    >
                      <Button>恢复链接</Button>
                    </Popconfirm>
                  )}
                </Space>
              )
            }
          ]}
        />
      </WorkSurface>
    </>
  );
}
