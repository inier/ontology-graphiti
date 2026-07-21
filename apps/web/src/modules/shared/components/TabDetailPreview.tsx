import { ClockCircleOutlined, LinkOutlined, FieldTimeOutlined, ReloadOutlined, PushpinOutlined } from '@ant-design/icons';
import { Button, Tooltip, Tag } from 'antd';
import { useLayoutStore } from '@/modules/shared/stores/layoutStore';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function TabDetailPreview() {
  const { t, instance } = useI18n('common');
  const { tabs, previewTabId, setActiveTab, addQuickAction, refreshTab, closeTab, toggleExtensionPanel } = useLayoutStore();

  const tab = tabs.find((t) => t.id === previewTabId);
  if (!tab) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: 'var(--odap-color-text-tertiary)' }}>
        <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.4 }}>📋</div>
        <div style={{ fontSize: 13 }}>{t('在左侧任务区点击 tab 查看详情')}</div>
      </div>
    );
  }

  const timeStr = new Date(tab.lastVisitedAt).toLocaleString(instance.language, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div style={{ padding: '12px 16px' }}>
      <div
        style={{
          fontSize: 15,
          fontWeight: 600,
          color: 'var(--odap-color-text-primary)',
          marginBottom: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 18 }}>{tab.icon || '📄'}</span>
        {tab.title}
      </div>

      <div style={{ marginBottom: 16 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: 'var(--odap-color-text-secondary)',
            marginBottom: 4,
          }}
        >
          <LinkOutlined />
          <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{tab.path}</span>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: 'var(--odap-color-text-secondary)',
            marginBottom: 4,
          }}
        >
          <FieldTimeOutlined />
          <span>{t('最后访问')}: {timeStr}</span>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            color: 'var(--odap-color-text-secondary)',
          }}
        >
          <ClockCircleOutlined />
          <span>{t('刷新次数')}: {tab.refreshToken}</span>
        </div>
        {tab.summary && (
          <div
            style={{
              marginTop: 8,
              padding: 8,
              background: 'var(--odap-color-bg-secondary)',
              borderRadius: 6,
              fontSize: 12,
              color: 'var(--odap-color-text-secondary)',
              lineHeight: 1.5,
            }}
          >
            {tab.summary}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Tooltip title={t('切换到该页面')}>
          <Button
            size="small"
            type="primary"
            icon={<LinkOutlined />}
            onClick={() => {
              setActiveTab(tab.id);
            }}
          >
            {t('切换')}
          </Button>
        </Tooltip>
        <Tooltip title={t('刷新')}>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => refreshTab(tab.id)}
          >
            {t('刷新')}
          </Button>
        </Tooltip>
        <Tooltip title={t('添加到快捷区')}>
          <Button
            size="small"
            icon={<PushpinOutlined />}
            onClick={() => addQuickAction(tab.id)}
          >
            {t('固定')}
          </Button>
        </Tooltip>
        <Tooltip title={t('关闭标签')}>
          <Button
            size="small"
            danger
            onClick={() => {
              closeTab(tab.id);
              toggleExtensionPanel();
            }}
          >
            {t('关闭')}
          </Button>
        </Tooltip>
      </div>

      <div style={{ marginTop: 12 }}>
        <Tag color={tab.active ? 'processing' : 'default'} style={{ fontSize: 11 }}>
          {tab.active ? t('Keep-Alive 活跃') : t('已缓存')}
        </Tag>
      </div>
    </div>
  );
}
