import { NodeIndexOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { logicApi } from '../services/businessApi';

export function Logic() {
  return (
    <BusinessEntityManager
      entityType="logic"
      title="逻辑"
      icon={<NodeIndexOutlined />}
      tagColor="purple"
      tagText="逻辑"
      api={logicApi}
      entityIdField="logic_id"
      showLogicExpression
    />
  );
}
