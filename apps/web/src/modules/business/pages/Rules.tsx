import { FileProtectOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { ruleApi } from '../services/businessApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function Rules() {
  const { t } = useI18n();
  return (
    <BusinessEntityManager
      entityType="rule"
      title={t('规则')}
      icon={<FileProtectOutlined />}
      tagColor="orange"
      tagText={t('规则')}
      api={ruleApi}
      entityIdField="rule_id"
      showRuleConditions
    />
  );
}
