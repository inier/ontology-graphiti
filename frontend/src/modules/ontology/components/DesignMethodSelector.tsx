import { useCallback } from 'react';
import { Card, Row, Col, Tag } from 'antd';
import { EditOutlined, DatabaseOutlined, MessageOutlined } from '@ant-design/icons';

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
  title: string;
  icon: React.ReactNode;
  description: string;
  recommended?: boolean;
}

const METHODS: MethodCard[] = [
  {
    key: 'manual',
    title: '手工定义',
    icon: <EditOutlined style={{ fontSize: 32, color: '#1677ff' }} />,
    description: '手动定义对象类型、关系类型、动作类型、业务过程、逻辑函数、规则和指标',
    recommended: true,
  },
  {
    key: 'database',
    title: '数据库抽取',
    icon: <DatabaseOutlined style={{ fontSize: 32, color: '#52c41a' }} />,
    description: '从外部数据库读取 Schema，自动映射为本体定义',
  },
  {
    key: 'natural_language',
    title: '自然语言提取',
    icon: <MessageOutlined style={{ fontSize: 32, color: '#722ed1' }} />,
    description: '输入自然语言描述，AI 自动提取对象、关系、规则和动作',
  },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function DesignMethodSelector({ onSelect, ontologyName }: DesignMethodSelectorProps) {
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
          选择设计方式
        </h2>
        <p style={{ margin: '8px 0 0', color: '#666' }}>
          为本体「{ontologyName}」选择一种定义方式
        </p>
      </div>

      <Row gutter={24} justify="center">
        {METHODS.map((method) => (
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
                <span style={{ fontSize: 16, fontWeight: 600 }}>{method.title}</span>
                {method.recommended && (
                  <Tag color="blue" style={{ marginLeft: 0 }}>
                    推荐
                  </Tag>
                )}
              </div>
              <p style={{ color: '#666', margin: 0, fontSize: 13, lineHeight: 1.6 }}>
                {method.description}
              </p>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}

export default DesignMethodSelector;
