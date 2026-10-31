/**
 * CognitionPage —— 认知引擎工作台页面（意图识别 / 解释链 / 角色视图）。
 *
 * 上下文注入：`CognitionPanel` 需要 workspace 与 scenario 作为解释请求的 context，
 * 页面负责从布局上下文取值，组件本身不依赖路由。
 */
import { useScenario, useWorkspace } from '@/modules/shared';
import CognitionPanel from '../components/CognitionPanel';

export function CognitionPage() {
  const { currentWorkspace } = useWorkspace();
  const { currentScenario } = useScenario();

  return (
    <div style={{ padding: 4 }}>
      <CognitionPanel workspaceId={currentWorkspace || 'default'} scenarioId={currentScenario || ''} />
    </div>
  );
}

export default CognitionPage;
