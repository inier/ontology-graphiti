import { Dropdown, Tooltip } from 'antd';
import { BgColorsOutlined, CheckOutlined } from '@ant-design/icons';
import type { ColorTheme } from '@/modules/shared/stores/layoutStore';
import { useLayoutStore } from '@/modules/shared/stores/layoutStore';

interface ThemeOption {
  key: ColorTheme;
  label: string;
  color: string;
  gradient: string;
}

const themeOptions: ThemeOption[] = [
  { key: 'indigo', label: '靛蓝 Indigo', color: '#6366F1', gradient: 'linear-gradient(135deg, #6366F1, #818CF8)' },
  { key: 'blue', label: '海蓝 Blue', color: '#3B82F6', gradient: 'linear-gradient(135deg, #3B82F6, #60A5FA)' },
  { key: 'green', label: '翠绿 Green', color: '#10B981', gradient: 'linear-gradient(135deg, #10B981, #34D399)' },
  { key: 'violet', label: '紫罗兰 Violet', color: '#8B5CF6', gradient: 'linear-gradient(135deg, #8B5CF6, #A78BFA)' },
  { key: 'amber', label: '琥珀 Amber', color: '#F59E0B', gradient: 'linear-gradient(135deg, #F59E0B, #FBBF24)' },
];

export function ThemeColorPicker() {
  const { colorTheme, setColorTheme } = useLayoutStore();
  const current = themeOptions.find((t) => t.key === colorTheme) || themeOptions[0];

  const items = themeOptions.map((opt) => ({
    key: opt.key,
    label: (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              display: 'inline-block',
              width: 14,
              height: 14,
              borderRadius: '50%',
              background: opt.gradient,
              boxShadow: `0 0 6px ${opt.color}44`,
            }}
          />
          {opt.label}
        </span>
        {colorTheme === opt.key && (
          <CheckOutlined style={{ color: opt.color, fontSize: 12 }} />
        )}
      </div>
    ),
    onClick: () => {
      setColorTheme(opt.key);
      document.documentElement.setAttribute('data-color-theme', opt.key);
      localStorage.setItem('odap-color-theme', opt.key);
    },
  }));

  return (
    <Dropdown menu={{ items }} trigger={['click']} placement="bottomRight">
      <Tooltip title="主题色">
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            width: 28,
            height: 28,
            borderRadius: '50%',
            background: current.gradient,
            boxShadow: `0 0 8px ${current.color}33`,
            transition: 'transform 200ms cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 200ms',
            fontSize: 14,
            color: '#fff',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.15)';
            e.currentTarget.style.boxShadow = `0 0 12px ${current.color}55`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)';
            e.currentTarget.style.boxShadow = `0 0 8px ${current.color}33`;
          }}
        >
          <BgColorsOutlined />
        </span>
      </Tooltip>
    </Dropdown>
  );
}
