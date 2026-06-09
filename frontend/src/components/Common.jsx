import { Button, Empty, Space, Tooltip, Typography, message } from "antd";
import { CopyOutlined } from "@ant-design/icons";

const { Text } = Typography;


export function PageHeader({ title, description, meta, actions }) {
  return (
    <div className="page-header">
      <div className="page-heading">
        <div className="page-heading-line">
          <h1>{title}</h1>
          {meta}
        </div>
        {description && <p>{description}</p>}
      </div>
      {actions && <Space wrap className="page-actions">{actions}</Space>}
    </div>
  );
}


export function WorkSurface({ toolbar, children, className = "" }) {
  return (
    <section className={`work-surface ${className}`.trim()}>
      {toolbar && <div className="filter-bar">{toolbar}</div>}
      {children}
    </section>
  );
}


export function EmptyState({ title, description, actions }) {
  return (
    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={null}>
      <div className="empty-copy">
        <strong>{title}</strong>
        {description && <span>{description}</span>}
      </div>
      {actions && <Space wrap>{actions}</Space>}
    </Empty>
  );
}


export function DateTime({ value }) {
  if (!value) {
    return <Text type="secondary">未同步</Text>;
  }
  return <span>{new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))}</span>;
}


export function EllipsisText({ children, width = 240 }) {
  if (!children) {
    return <Text type="secondary">无</Text>;
  }
  return (
    <Tooltip title={children}>
      <span className="ellipsis-text" style={{ maxWidth: width }}>{children}</span>
    </Tooltip>
  );
}


export function CopyButton({ text, label = "复制" }) {
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      message.success("已复制到剪贴板");
    } catch {
      message.error("复制失败，请手动复制");
    }
  }

  return (
    <Tooltip title={label}>
      <Button aria-label={label} icon={<CopyOutlined />} onClick={copy} />
    </Tooltip>
  );
}
