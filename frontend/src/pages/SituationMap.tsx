import { useState } from 'react';
import { Row, Col, Card } from 'antd';
import { MapView } from '../components/MapView';

interface MapUnit {
  id: string;
  name: string;
  side: 'red' | 'blue' | 'neutral';
  position: [number, number];
  type: string;
  status?: string;
}

export function SituationMap() {
  const [units] = useState<MapUnit[]>([
    { id: '1', name: '红方装甲营', side: 'red', position: [39.9, 116.4], type: 'armor', status: 'engaged' },
    { id: '2', name: '红方步兵连', side: 'red', position: [39.92, 116.38], type: 'infantry', status: 'moving' },
    { id: '3', name: '蓝方机械化步兵营', side: 'blue', position: [39.85, 116.42], type: 'mechanized_infantry', status: 'engaged' },
    { id: '4', name: '蓝方炮兵连', side: 'blue', position: [39.88, 116.45], type: 'artillery', status: 'idle' },
  ]);
  const [showTerrain, setShowTerrain] = useState(true);
  const [showWeather] = useState(false);
  const [showTracks, setShowTracks] = useState(true);

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <MapView
            units={units}
            showTerrain={showTerrain}
            showWeather={showWeather}
            showTracks={showTracks}
            onToggleLayer={(layer, visible) => {
              if (layer === 'terrain') setShowTerrain(visible);
              if (layer === 'tracks') setShowTracks(visible);
            }}
          />
        </Col>
      </Row>
    </div>
  );
}
