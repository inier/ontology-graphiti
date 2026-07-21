import { NodeIndexOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { logicApi } from '../services/businessApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function Logic() {
  const { t } = useI18n();
  return (
    <BusinessEntityManager
      entityType="logic"
      title={t('逻辑')}
      icon={<NodeIndexOutlined />}
      tagColor="purple"
      tagText={t('逻辑')}
      api={logicApi}
      entityIdField="logic_id"
      showLogicExpression
    />
  );
}
