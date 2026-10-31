/**
 * 强调色相选择器（W0-1 / AC-44）
 *
 * v2 变更：
 *  - 删除 5 套旧调色板（含 violet）与全部线性渐变（P0-2）
 *  - 选项色块直接读 Token 变量，纯色圆点；选中态为描边环 + 对勾图标
 *  - 过渡改用 Token 缓动，无过冲（AC-46）
 */
import { Dropdown, Tooltip } from 'antd';
import type { ColorTheme } from '@/modules/shared/stores/layoutStore';
import { useLayoutStore } from '@/modules/shared/stores/layoutStore';
import { Icon } from './Icon';
import { resolveAccent, type AccentHue } from '../styles/colorThemeUtils';

interface ThemeOption {
  key: ColorTheme;
  label: string;
  hue: AccentHue;
}

/** 仅 4 个纯色色相（UIUX §3.4）；violet 已退役，旧持久化值由 resolveAccent 兜底映射到 indigo */
const themeOptions: ThemeOption[] = [
  { key: 'indigo', label: '靛蓝 Indigo', hue: 'indigo' },
  { key: 'blue', label: '钴蓝 Cobalt', hue: 'cobalt' },
  { key: 'green', label: '青绿 Teal', hue: 'teal' },
  { key: 'amber', label: '石墨 Graphite', hue: 'graphite' },
];

const swatch = (hue: AccentHue) => `var(--odap-primitive-${hue}-600)`;

export function ThemeColorPicker() {
  const { colorTheme, setColorTheme } = useLayoutStore();
  const currentHue = resolveAccent(colorTheme);

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
              borderRadius: 'var(--odap-radius-pill)',
              background: swatch(opt.hue),
            }}
          />
          {opt.label}
        </span>
        {currentHue === opt.hue && <Icon role="confirm" size={16} />}
      </div>
    ),
    onClick: () => {
      setColorTheme(opt.key);
      // applyColorTheme 由 layout 的 effect 统一写入 data-accent / data-appearance
    },
  }));

  return (
    <Dropdown menu={{ items }} trigger={['click']} placement="bottomRight">
      <Tooltip title="强调色">
        <button
          type="button"
          aria-label="选择强调色"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            width: 'var(--odap-size-control-md)',
            height: 'var(--odap-size-control-md)',
            padding: 0,
            borderRadius: 'var(--odap-radius-pill)',
            background: swatch(currentHue),
            border: 'none',
            color: 'var(--odap-color-accent-on)',
            transition:
              'transform var(--odap-duration-fast) var(--odap-ease-standard), box-shadow var(--odap-duration-fast) var(--odap-ease-standard)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = 'var(--odap-focus-ring)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <Icon role="palette" size={16} />
        </button>
      </Tooltip>
    </Dropdown>
  );
}
