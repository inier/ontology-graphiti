import { useEffect, useRef, useState } from 'react';
import { createViewer, type ViewerInstance } from 'jit-viewer';
import 'jit-viewer/style.css';
import { Empty, Spin, Typography } from 'antd';
import { FileUnknownOutlined } from '@ant-design/icons';

const { Text } = Typography;

/**
 * jit-viewer 支持预览的文件扩展名
 */
const SUPPORTED_EXTENSIONS = new Set([
  'pdf', 'docx', 'xlsx', 'xls', 'pptx', 'ppt',
  'ofd', 'txt', 'md', 'markdown', 'csv',
]);

/**
 * 根据 file_url 或 file_type 推断文件扩展名
 * 对于含查询参数的 URL（如 MinIO presigned URL），先从路径部分提取扩展名
 */
function resolveExtension(fileUrl?: string, fileType?: string, filename?: string): string {
  // 优先从 URL/路径提取扩展名（先去掉查询参数再匹配）
  if (fileUrl) {
    const pathPart = fileUrl.split('?')[0].split('#')[0];
    const match = pathPart.match(/\.([a-zA-Z0-9]+)$/);
    if (match) return match[1].toLowerCase();
  }
  // 从文件名提取
  if (filename) {
    const match = filename.match(/\.([a-zA-Z0-9]+)$/);
    if (match) return match[1].toLowerCase();
  }
  // 从 MIME 类型映射
  if (fileType) {
    const mimeExtMap: Record<string, string> = {
      'application/pdf': 'pdf',
      'application/x-pdf': 'pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
      'application/msword': 'docx',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
      'application/vnd.ms-excel': 'xlsx',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
      'application/vnd.ms-powerpoint': 'pptx',
      'application/ofd': 'ofd',
      'text/plain': 'txt',
      'text/markdown': 'md',
      'text/csv': 'csv',
      'text/html': 'txt',
      'application/json': 'txt',
      'application/rtf': 'txt',
      'text/rtf': 'txt',
    };
    return mimeExtMap[fileType] || '';
  }
  return '';
}

/**
 * 根据内容类型判断是否支持预览
 */
function isPreviewSupported(fileUrl?: string, fileType?: string, filename?: string): boolean {
  const ext = resolveExtension(fileUrl, fileType, filename);
  return SUPPORTED_EXTENSIONS.has(ext);
}

export interface DocumentViewerProps {
  /** 文件的 URL 地址（后端返回的 file_url，可能是 MinIO key 或本地路径） */
  fileUrl?: string;
  /** MinIO presigned URL（可直接在浏览器访问的完整 URL） */
  presignedUrl?: string;
  /** 文件名（用于显示和类型检测） */
  filename?: string;
  /** MIME 类型 */
  fileType?: string;
  /** 容器高度，默认 500 */
  height?: number | string;
  /** 主题，默认 light */
  theme?: 'light' | 'dark';
}

/**
 * 通用文档预览组件
 *
 * 基于 jit-viewer SDK，支持 PDF、Word、Excel、PPT、Markdown、TXT 等格式的在线预览。
 * 支持 MinIO presigned URL 和本地静态文件两种来源。
 * 不支持的格式会显示"暂未支持"提示。
 */
export function DocumentViewer({
  fileUrl,
  presignedUrl,
  filename,
  fileType,
  height = 500,
  theme = 'light',
}: DocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<ViewerInstance | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error' | 'unsupported'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  // 实际用于获取文件的 URL：优先使用 presignedUrl（MinIO），否则用 fileUrl（本地静态）
  const fetchUrl = presignedUrl || fileUrl;
  // 检查是否支持预览（使用 fileUrl 和 filename 做扩展名检测，而非 presigned URL 的查询参数）
  const supported = fetchUrl && isPreviewSupported(fileUrl, fileType, filename);

  useEffect(() => {
    if (!supported) {
      setStatus('unsupported');
      return;
    }

    if (!containerRef.current || !fetchUrl) return;

    const container = containerRef.current;
    let mounted = true;

    const initViewer = async () => {
      try {
        // 确保 filename 包含正确的扩展名，否则 jit-viewer 无法识别文件类型
        const ext = resolveExtension(fileUrl, fileType, filename);
        const rawName = filename || (fileUrl ? fileUrl.split('/').pop() : 'document') || 'document';
        const viewerFilename = (ext && !rawName.match(/\.[a-zA-Z0-9]+$/))
          ? `${rawName}.${ext}`
          : rawName;

        const viewer = createViewer({
          target: container,
          file: fetchUrl!,
          filename: viewerFilename,
          theme,
          toolbar: true,
          width: '100%',
          height: typeof height === 'number' ? `${height}px` : height,
          locale: 'zh-CN',
          onReady: () => {
            if (mounted) setStatus('ready');
          },
          onLoad: () => {
            if (mounted) setStatus('ready');
          },
          onError: (error: Error) => {
            if (mounted) {
              setStatus('error');
              setErrorMsg(error.message || '文档加载失败');
            }
          },
        });

        viewerRef.current = viewer;
        await viewer.mount();
      } catch (e: unknown) {
        if (mounted) {
          setStatus('error');
          setErrorMsg(e instanceof Error ? e.message : '文档预览初始化失败');
        }
      }
    };

    initViewer();

    return () => {
      mounted = false;
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
  }, [fetchUrl, supported, filename, theme, height]);

  // 不支持预览的格式
  if (!supported) {
    return (
      <div
        style={{
          height: typeof height === 'number' ? `${height}px` : height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#fafafa',
          borderRadius: 8,
          border: '1px solid #f0f0f0',
        }}
      >
        <Empty
          image={<FileUnknownOutlined style={{ fontSize: 48, color: '#bfbfbf' }} />}
          imageStyle={{ height: 60 }}
          description={
            <div>
              <Text type="secondary" style={{ fontSize: 14 }}>
                该文件格式暂未支持预览
              </Text>
              {fileType && (
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    文件类型：{fileType}
                  </Text>
                </div>
              )}
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }}>
      {status === 'loading' && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(255,255,255,0.8)',
            zIndex: 10,
            borderRadius: 8,
          }}
        >
          <Spin tip="正在加载文档..." />
        </div>
      )}
      {status === 'error' && (
        <div
          style={{
            height: typeof height === 'number' ? `${height}px` : height,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: '#fff2f0',
            borderRadius: 8,
            border: '1px solid #ffccc7',
          }}
        >
          <Empty
            description={
              <div>
                <Text type="danger">文档加载失败</Text>
                {errorMsg && (
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>{errorMsg}</Text>
                  </div>
                )}
              </div>
            }
          />
        </div>
      )}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: typeof height === 'number' ? `${height}px` : height,
          borderRadius: 8,
          overflow: 'hidden',
        }}
      />
    </div>
  );
}
