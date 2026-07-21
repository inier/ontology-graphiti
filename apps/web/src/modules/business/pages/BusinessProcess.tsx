import { BranchesOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { processApi } from '../services/businessApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function BusinessProcess() {
  const { t } = useI18n();
  return (
    <BusinessEntityManager
      entityType="process"
      title={t('业务过程')}
      icon={<BranchesOutlined />}
      tagColor="green"
      tagText={t('过程')}
      api={processApi}
      entityIdField="process_id"
      showFlowNodes
    />
  );
}
