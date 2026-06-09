import { Button, Result } from "antd";
import { Link } from "react-router-dom";


export default function NotFoundPage() {
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="当前地址没有对应的管理页面。"
      extra={<Link to="/"><Button type="primary">返回仪表盘</Button></Link>}
    />
  );
}
