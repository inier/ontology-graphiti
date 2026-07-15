import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';

interface StatCardProps {
  title: string;
  value: number | string;
  trend?: number;
  suffix?: string;
  loading?: boolean;
}

export function StatCard({ title, value, trend, suffix, loading }: StatCardProps) {
  const trendColor = trend && trend > 0
    ? 'var(--odap-color-success)'
    : trend && trend < 0
      ? 'var(--odap-color-error)'
      : 'var(--odap-color-text-tertiary)';
  const TrendIcon = trend && trend > 0 ? ArrowUpOutlined : ArrowDownOutlined;

  return (
    <div className="stat-card">
      <div className="stat-label">{title}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span className="stat-value">
          {loading ? '-' : value}
        </span>
        {suffix && (
          <span style={{ fontSize: 14, color: 'var(--odap-color-text-secondary)' }}>
            {suffix}
          </span>
        )}
      </div>
      {trend !== undefined && !loading && (
        <div className={`stat-trend ${trend > 0 ? 'up' : 'down'}`}>
          <TrendIcon />
          <span>{Math.abs(trend).toFixed(1)}%</span>
          <span style={{ color: 'var(--odap-color-text-tertiary)', marginLeft: 4, fontWeight: 400 }}>
            较上周
          </span>
        </div>
      )}
    </div>
  );
}
