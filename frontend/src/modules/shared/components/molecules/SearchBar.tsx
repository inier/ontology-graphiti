import type { FC, CSSProperties } from 'react';
import { Space } from 'antd';
import adapter from '../adapter';

interface SearchBarProps {
  value?: string;
  onChange?: (value: string) => void;
  onSearch?: (value: string) => void;
  placeholder?: string;
  buttonText?: string;
  loading?: boolean;
  size?: 'small' | 'middle' | 'large';
  className?: string;
  style?: CSSProperties;
}

const AdapterButton = adapter.getButton();
const AdapterInput = adapter.getInput();

const SearchBar: FC<SearchBarProps> = ({
  value,
  onChange,
  onSearch,
  placeholder = 'Search...',
  buttonText = 'Search',
  loading,
  size = 'middle',
  className,
  style,
}) => {
  const handleSearch = () => {
    onSearch?.(value || '');
  };

  return (
    <Space.Compact className={className} style={style}>
      <AdapterInput
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        size={size}
      />
      <AdapterButton type="primary" onClick={handleSearch} loading={loading} size={size}>
        {buttonText}
      </AdapterButton>
    </Space.Compact>
  );
};

export default SearchBar;
