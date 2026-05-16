import { BranchesOutlined } from '@ant-design/icons';
import { BusinessEntityManager } from '../components/BusinessEntityManager';
import { processApi } from '../services/businessApi';

export function BusinessProcess() {
  return (
    <BusinessEntityManager
      entityType="process"
      title="业务过程"
      icon={<BranchesOutlined />}
      tagColor="green"
      tagText="过程"
      api={processApi}
      entityIdField="process_id"
      showFlowNodes
    />
  );
}
