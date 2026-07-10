import { useState } from 'react';
import { Card, Tabs, Alert, Button, Typography, Space, Spin } from 'antd';
import {
  CloudServerOutlined, ReloadOutlined, ExpandOutlined,
  DatabaseOutlined, InboxOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

/** MinIO Console 代理路径（与后端 proxy 挂载路径一致） */
const MINIO_CONSOLE_PROXY = '/minio-console/';

export function MinioAdminPage() {
  const [iframeError, setIframeError] = useState(false);
  const [iframeLoading, setIframeLoading] = useState(true);
  const [iframeKey, setIframeKey] = useState(0);

  const handleReload = () => {
    setIframeLoading(true);
    setIframeError(false);
    setIframeKey(prev => prev + 1);
  };

  const handleOpenInNewTab = () => {
    window.open(MINIO_CONSOLE_PROXY, '_blank', 'noopener,noreferrer');
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <CloudServerOutlined style={{ marginRight: 8 }} />
          对象存储管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={handleReload}>
            刷新
          </Button>
          <Button icon={<ExpandOutlined />} onClick={handleOpenInNewTab}>
            新窗口打开
          </Button>
        </Space>
      </div>

      <Tabs
        defaultActiveKey="console"
        items={[
          {
            key: 'console',
            label: (
              <span>
                <InboxOutlined /> MinIO Console
              </span>
            ),
            children: (
              <Card
                styles={{ body: { padding: 0 }}}
                style={{ overflow: 'hidden' }}
              >
                {iframeError && (
                  <Alert
                    type="error"
                    showIcon
                    title="MinIO Console 加载失败"
                    description="请检查 MinIO 容器是否正常运行（podman ps graphiti-minio），以及后端代理是否正常。"
                    action={<Button onClick={handleReload}>重试</Button>}
                    style={{ margin: 16 }}
                  />
                )}

                {iframeLoading && !iframeError && (
                  <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: 200,
                  }}>
                    <Spin size="large" description="正在加载 MinIO Console..." />
                  </div>
                )}

                <iframe
                  key={iframeKey}
                  src={MINIO_CONSOLE_PROXY}
                  title="MinIO Console"
                  style={{
                    width: '100%',
                    height: 'calc(100vh - 240px)',
                    minHeight: 600,
                    border: 'none',
                    display: iframeError ? 'none' : 'block',
                  }}
                  onLoad={() => setIframeLoading(false)}
                  onError={() => {
                    setIframeLoading(false);
                    setIframeError(true);
                  }}
                />
              </Card>
            ),
          },
          {
            key: 'about',
            label: (
              <span>
                <DatabaseOutlined /> 关于
              </span>
            ),
            children: (
              <Card>
                <div style={{ maxWidth: 640 }}>
                  <Text>
                    此处嵌入了 MinIO Console 管理界面，提供完整的对象存储管理功能，包括：
                  </Text>
                  <ul style={{ marginTop: 12, paddingLeft: 20, lineHeight: 2 }}>
                    <li>存储桶管理（创建、查看、删除）</li>
                    <li>文件浏览与目录导航</li>
                    <li>文件上传与下载</li>
                    <li>对象元数据查看</li>
                    <li>访问策略配置</li>
                    <li>用户与权限管理</li>
                  </ul>
                  <div style={{ marginTop: 16 }}>
                    <Text type="secondary">
                      MinIO Console 通过后端反向代理嵌入，自动完成认证登录。
                      所有操作受平台权限管控，仅管理员可访问。
                    </Text>
                  </div>
                </div>
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}

export default MinioAdminPage;
