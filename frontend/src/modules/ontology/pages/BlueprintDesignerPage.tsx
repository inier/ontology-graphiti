import { BlueprintDesigner } from '../components/blueprint/BlueprintDesigner';
import { PageTourWrapper, blueprintTourSteps, PAGE_IDS } from '@/modules/guide';

export function BlueprintDesignerPage() {
  return (
    <PageTourWrapper pageId={PAGE_IDS.BLUEPRINT} steps={blueprintTourSteps}>
    <div style={{ height: '100vh', overflow: 'hidden' }}>
      <BlueprintDesigner />
    </div>
    </PageTourWrapper>
  );
}
