import { Alert } from 'antd';
import { SimulatorConsole } from '../components/SimulatorConsole';

export function Simulator() {
  return (
    <div>
      <Alert
        message="模拟推演"
        description="配置参数并开始推演，实时监控双方战力变化和伤亡情况"
        type="info"
        showIcon
        style={{ marginBottom: 16, borderRadius: 8 }}
      />
      <SimulatorConsole />
    </div>
  );
}
