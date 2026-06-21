import { useCallback } from 'react';
import { Row, Col, Tag } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { EditOutlined, DatabaseOutlined, MessageOutlined } from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type DesignMethod = 'manual' | 'database' | 'natural_language';

export interface DesignMethodSelectorProps {
  onSelect: (method: DesignMethod) => void;
  ontologyName: string;
}

/* ------------------------------------------------------------------ */
/*  Method card definitions                                            */
/* ------------------------------------------------------------------ */

interface MethodCard {
  key: DesignMethod;
  titleKey: string;
  icon: React.ReactNode;
  descKey: string;
  recommended?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function DesignMethodSelector({ onSelect, ontologyName }: DesignMethodSelectorProps) {
  const { t } = useI18n('ontology');

  const methods: MethodCard[] = [
    {
      key: 'manual',
      titleKey: 'designMethod.manual',
      icon: <EditOutlined style={{ fontSize: 32, color: '#1677ff' }} />,
      descKey: 'designMethod.manualDesc',
      recommended: true,
    },
    {
      key: 'database',
      titleKey: 'designMethod.database',
      icon: <DatabaseOutlined style={{ fontSize: 32, color: '#52c41a' }} />,
      descKey: 'designMethod.databaseDesc',
    },
    {
      key: 'natural_language',
      titleKey: 'designMethod.naturalLanguage',
      icon: <MessageOutlined style={{ fontSize: 32, color: '#722ed1' }} />,
      descKey: 'designMethod.naturalLanguageDesc',
    },
  ];

  const handleCardClick = useCallback(
    (method: DesignMethod) => {
      onSelect(method);
    },
    [onSelect],
  );

  return (
    <div style={{ padding: '24px 0' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
          {t('designMethod.title')}
        </h2>
        <p style={{ margin: '8px 0 0', color: '#666' }}>
          {t('designMethod.subtitle', { name: ontologyName })}
        </p>
      </div>

      <Row gutter={24} justify="center">
        {methods.map((method) => (
          <Col span={8} key={method.key}>
            <Card
              hoverable
              style={{
                cursor: 'pointer',
                textAlign: 'center',
                height: '100%',
                transition: 'border-color 0.2s, box-shadow 0.2s',
              }}
              styles={{
                body: { padding: '32px 24px' },
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#1677ff';
                e.currentTarget.style.boxShadow = '0 2px 12px rgba(22, 119, 255, 0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#d9d9d9';
                e.currentTarget.style.boxShadow = 'none';
              }}
              onClick={() => handleCardClick(method.key)}
            >
              <div style={{ marginBottom: 16 }}>{method.icon}</div>
              <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <span style={{ fontSize: 16, fontWeight: 600 }}>{t(method.titleKey)}</span>
                {method.recommended && (
                  <Tag color="blue" style={{ marginLeft: 0 }}>
                    {t('designMethod.recommended')}
                  </Tag>
                )}
              </div>
              <p style={{ color: '#666', margin: 0, fontSize: 13, lineHeight: 1.6 }}>
                {t(method.descKey)}
              </p>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}

export default DesignMethodSelector;
