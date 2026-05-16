import { FileProtectOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { ruleApi } from '../services/businessApi';

export function Rules() {
  return (
    <BusinessEntityManager
      entityType="rule"
      title="规则"
      icon={<FileProtectOutlined />}
      tagColor="orange"
      tagText="规则"
      api={ruleApi}
      entityIdField="rule_id"
      showRuleConditions
    />
  );
}
