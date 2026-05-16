import { FundOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { indicatorApi } from '../services/businessApi';

export function Indicators() {
  return (
    <BusinessEntityManager
      entityType="indicator"
      title="指标"
      icon={<FundOutlined />}
      tagColor="blue"
      tagText="指标"
      api={indicatorApi}
      entityIdField="indicator_id"
      showIndicatorConfig
    />
  );
}
