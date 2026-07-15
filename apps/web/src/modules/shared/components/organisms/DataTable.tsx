import type { CSSProperties, ReactNode } from 'react';
import { useState, useMemo } from 'react';
import adapter from '../adapter';
import type { TableProps } from '../adapter';

interface DataTableProps<T extends object> {
  columns: TableProps<T>['columns'];
  dataSource: T[];
  loading?: boolean;
  rowKey?: string | ((record: T) => string);
  pagination?: false | { pageSize?: number; current?: number; total?: number };
  searchable?: boolean;
  searchPlaceholder?: string;
  onSearch?: (value: string) => void;
  onRowClick?: (record: T) => void;
  title?: string;
  toolbar?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const AdapterTable = adapter.getTable();
const AdapterInput = adapter.getInput();
const AdapterButton = adapter.getButton();

function DataTable<T extends object>(props: DataTableProps<T>) {
  const {
    columns,
    dataSource,
    loading = false,
    rowKey = 'id',
    pagination,
    searchable = false,
    searchPlaceholder = 'Search...',
    onSearch,
    onRowClick,
    title,
    toolbar,
    className,
    style,
  } = props;

  const [searchValue, setSearchValue] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  void onRowClick;

  const filteredData = useMemo(() => {
    if (!searchValue || !searchable) return dataSource;
    const lowerSearch = searchValue.toLowerCase();
    return dataSource.filter((item) =>
      Object.values(item).some((val) =>
        String(val).toLowerCase().includes(lowerSearch)
      )
    );
  }, [dataSource, searchValue, searchable]);

  const handleSearch = () => {
    if (onSearch) {
      onSearch(searchValue);
    }
  };

  const paginationConfig = pagination === false
    ? false
    : {
        current: currentPage,
        pageSize: pageSize,
        total: pagination?.total ?? filteredData.length,
        showSizeChanger: true,
        showTotal: (total: number) => `Total ${total} items`,
        onChange: (page: number, size: number) => {
          setCurrentPage(page);
          setPageSize(size);
        },
      };

  return (
    <div className={className} style={style}>
      {(title || searchable || toolbar) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, alignItems: 'center' }}>
          {title && <h3 style={{ margin: 0 }}>{title}</h3>}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {searchable && (
              <div style={{ display: 'flex', gap: 4 }}>
                <AdapterInput
                  value={searchValue}
                  onChange={setSearchValue}
                  placeholder={searchPlaceholder}
                  size="small"
                />
                <AdapterButton type="primary" onClick={handleSearch} size="small">
                  Search
                </AdapterButton>
              </div>
            )}
            {toolbar}
          </div>
        </div>
      )}
      <AdapterTable<T>
        columns={columns}
        dataSource={filteredData}
        loading={loading}
        pagination={paginationConfig}
        rowKey={rowKey}
      />
    </div>
  );
}

export default DataTable as <T extends object>(props: DataTableProps<T>) => React.JSX.Element;
