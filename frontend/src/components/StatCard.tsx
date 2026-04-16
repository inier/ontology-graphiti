import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

interface StatCardProps {
  title: string;
  value: number | string;
  trend?: number;
  suffix?: string;
  loading?: boolean;
}

export function StatCard({ title, value, trend, suffix, loading }: StatCardProps) {
  const trendColor = trend && trend > 0 ? '#52c41a' : trend && trend < 0 ? '#ff4d4f' : '#8c8c8c';
  const TrendIcon = trend && trend > 0 ? ArrowUpOutlined : ArrowDownOutlined;

  return (
    <div
      style={{
        background: '#ffffff',
        borderRadius: 8,
        padding: 20,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        transition: 'box-shadow 0.3s',
      }}
    >
      <div style={{ fontSize: 14, color: '#8c8c8c', marginBottom: 8 }}>{title}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span
          style={{
            fontSize: 32,
            fontWeight: 600,
            color: '#262626',
            fontFamily: "'SF Mono', 'Menlo', monospace",
          }}
        >
          {loading ? '-' : value}
        </span>
        {suffix && <span style={{ fontSize: 14, color: '#8c8c8c' }}>{suffix}</span>}
      </div>
      {trend !== undefined && !loading && (
        <div style={{ marginTop: 8, fontSize: 12, color: trendColor, display: 'flex', alignItems: 'center', gap: 4 }}>
          <TrendIcon />
          <span>{Math.abs(trend).toFixed(1)}%</span>
          <span style={{ color: '#8c8c8c', marginLeft: 4 }}>较上周</span>
        </div>
      )}
    </div>
  );
}
