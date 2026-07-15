import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Spin, Typography, Empty, Button, Space } from 'antd';
import { ReloadOutlined, ExpandOutlined } from '@ant-design/icons';

const { Title } = Typography;

/**
 * 通用 iframe 查看器
 * 路由: /iframe-viewer?url=<encoded_url>&title=<encoded_title>
 * 用于在平台内嵌入外部系统（如 MinIO Console）
 */
export function IframeViewerPage() {
  const [searchParams] = useSearchParams();
  const url = searchParams.get('url') || '';
  const title = searchParams.get('title') || '外部页面';

  const decodedUrl = useMemo(() => {
    try { return decodeURIComponent(url); } catch { return url; }
  }, [url]);

  const decodedTitle = useMemo(() => {
    try { return decodeURIComponent(title); } catch { return title; }
  }, [title]);

  if (!decodedUrl) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Empty description="未指定页面地址（缺少 url 参数）" />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        padding: '12px 24px',
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#fff',
      }}>
        <Title level={5} style={{ margin: 0 }}>{decodedTitle}</Title>
        <Space>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => {
              const iframe = document.getElementById('odap-iframe') as HTMLIFrameElement;
              if (iframe) iframe.src = iframe.src;
            }}
          >
            刷新
          </Button>
          <Button
            size="small"
            icon={<ExpandOutlined />}
            onClick={() => window.open(decodedUrl, '_blank')}
          >
            新窗口
          </Button>
        </Space>
      </div>
      <div style={{ flex: 1, position: 'relative' }}>
        <iframe
          id="odap-iframe"
          src={decodedUrl}
          title={decodedTitle}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            position: 'absolute',
            top: 0,
            left: 0,
          }}
          allow="clipboard-read; clipboard-write"
        />
      </div>
    </div>
  );
}

export default IframeViewerPage;
