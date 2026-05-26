import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined, SafetyCertificateOutlined, ApartmentOutlined, TeamOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useAuthStore } from '../stores/authStore';

export function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success('登录成功');
      navigate('/');
    } catch {
      message.error('登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { icon: <ApartmentOutlined />, title: '本体建模', desc: '多领域本体驱动，知识图谱可视化构建' },
    { icon: <ThunderboltOutlined />, title: '智能决策', desc: 'Agent 协同推理，OODA 循环决策引擎' },
    { icon: <SafetyCertificateOutlined />, title: '策略治理', desc: 'OPA 策略引擎，细粒度权限管控' },
    { icon: <TeamOutlined />, title: '角色协同', desc: '多角色工作空间，任务智能分配' },
  ];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: '#fff' }}>
      <div
        style={{
          flex: 1,
          background: 'linear-gradient(135deg, #0a1628 0%, #1a3a5c 50%, #0d2137 100%)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '60px 80px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: -120,
            right: -120,
            width: 400,
            height: 400,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(22,119,255,0.15) 0%, transparent 70%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: -80,
            left: -80,
            width: 300,
            height: 300,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(250,173,20,0.1) 0%, transparent 70%)',
          }}
        />
        <div style={{ position: 'relative', zIndex: 1, maxWidth: 520 }}>
          <div style={{ marginBottom: 48 }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 56,
                height: 56,
                borderRadius: 14,
                background: 'linear-gradient(135deg, #1677ff, #4096ff)',
                marginBottom: 24,
                boxShadow: '0 4px 16px rgba(22,119,255,0.4)',
              }}
            >
              <ApartmentOutlined style={{ fontSize: 28, color: '#fff' }} />
            </div>
            <h1 style={{ fontSize: 42, fontWeight: 800, color: '#fff', margin: 0, letterSpacing: -1 }}>
              ODAP
            </h1>
            <p style={{ fontSize: 18, color: 'rgba(255,255,255,0.65)', marginTop: 12, lineHeight: 1.6 }}>
              本体驱动分析决策平台
            </p>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.4)', marginTop: 8, lineHeight: 1.8 }}>
              Ontology-Driven Analysis & Decision Platform
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            {features.map((f) => (
              <div
                key={f.title}
                style={{
                  padding: '20px 16px',
                  borderRadius: 12,
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  transition: 'all 0.3s',
                }}
              >
                <div style={{ fontSize: 22, color: '#4096ff', marginBottom: 10 }}>{f.icon}</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'rgba(255,255,255,0.9)', marginBottom: 4 }}>
                  {f.title}
                </div>
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', lineHeight: 1.6 }}>{f.desc}</div>
              </div>
            ))}
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            bottom: 32,
            left: 0,
            right: 0,
            textAlign: 'center',
            color: 'rgba(255,255,255,0.2)',
            fontSize: 12,
          }}
        >
          Powered by Graphiti · OpenHarness · OPA
        </div>
      </div>

      <div
        style={{
          width: 460,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '60px 56px',
          background: '#fff',
        }}
      >
        <div style={{ marginBottom: 40 }}>
          <h2 style={{ fontSize: 26, fontWeight: 700, color: '#1a1a1a', margin: 0 }}>欢迎回来</h2>
          <p style={{ fontSize: 14, color: '#8c8c8c', marginTop: 8 }}>登录以访问您的工作空间</p>
        </div>
        <Form layout="vertical" onFinish={onFinish} autoComplete="off" size="large" initialValues={{ username: 'admin', password: 'admin123' }}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input
              prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
              placeholder="用户名"
              style={{ height: 48, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
              placeholder="密码"
              style={{ height: 48, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{
                height: 48,
                borderRadius: 10,
                fontSize: 16,
                fontWeight: 600,
                background: 'linear-gradient(135deg, #1677ff, #4096ff)',
                border: 'none',
                boxShadow: '0 4px 12px rgba(22,119,255,0.35)',
              }}
            >
              登 录
            </Button>
          </Form.Item>
        </Form>
        <div style={{ marginTop: 32, padding: '16px 20px', background: '#f6f8fa', borderRadius: 10 }}>
          <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 6 }}>演示账号</div>
          <div style={{ fontSize: 13, color: '#595959' }}>
            用户名 <span style={{ fontWeight: 600, color: '#1677ff' }}>admin</span>
            &nbsp;&nbsp;密码 <span style={{ fontWeight: 600, color: '#1677ff' }}>admin123</span>
          </div>
        </div>
      </div>
    </div>
  );
}
