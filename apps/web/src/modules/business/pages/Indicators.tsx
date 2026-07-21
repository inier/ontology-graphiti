import { FundOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { indicatorApi } from '../services/businessApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function Indicators() {
  const { t } = useI18n();
  return (
    <BusinessEntityManager
      entityType="indicator"
      title={t('指标')}
      icon={<FundOutlined />}
      tagColor="blue"
      tagText={t('指标')}
      api={indicatorApi}
      entityIdField="indicator_id"
      showIndicatorConfig
    />
  );
}
