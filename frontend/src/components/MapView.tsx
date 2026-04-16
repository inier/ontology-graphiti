import { useEffect, useRef } from 'react';
import { Card, Checkbox, Space } from 'antd';

interface MapUnit {
  id: string;
  name: string;
  side: 'red' | 'blue' | 'neutral';
  position: [number, number];
  type: string;
  status?: string;
}

interface MapViewProps {
  units: MapUnit[];
  showTerrain?: boolean;
  showWeather?: boolean;
  showTracks?: boolean;
  onToggleLayer?: (layer: string, visible: boolean) => void;
}

export function MapView({ units, showTerrain, showWeather, showTracks, onToggleLayer }: MapViewProps) {
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mapRef.current || units.length === 0) return;

    const drawMap = async () => {
      const L = await import('leaflet');

      mapRef.current!.innerHTML = '';

      const map = L.map(mapRef.current!).setView([39.9, 116.4], 10);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(map);

      const sideColors: Record<string, string> = {
        red: '#ff4d4f',
        blue: '#1890ff',
        neutral: '#8c8c8c',
      };

      units.forEach((unit) => {
        const color = sideColors[unit.side] || '#8c8c8c';

        const icon = L.divIcon({
          className: 'custom-marker',
          html: `
            <div style="
              width: 24px;
              height: 24px;
              border-radius: 50%;
              background: ${color};
              border: 3px solid #fff;
              box-shadow: 0 2px 8px rgba(0,0,0,0.3);
              display: flex;
              align-items: center;
              justify-content: center;
              color: #fff;
              font-size: 10px;
              font-weight: bold;
            ">
              ${unit.side === 'red' ? 'R' : unit.side === 'blue' ? 'B' : 'N'}
            </div>
          `,
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        });

        const marker = L.marker(unit.position, { icon })
          .addTo(map)
          .bindPopup(`
            <div style="min-width: 150px;">
              <h4 style="margin: 0 0 8px; font-size: 14px;">${unit.name}</h4>
              <div style="font-size: 12px; color: #666;">
                <div><strong>类型:</strong> ${unit.type}</div>
                <div><strong>状态:</strong> ${unit.status || '未知'}</div>
                <div><strong>位置:</strong> ${unit.position.join(', ')}</div>
              </div>
            </div>
          `);

        if (showTracks) {
          const track: [number, number][] = [
            [unit.position[0] - 0.05, unit.position[1] - 0.05],
            unit.position,
          ];
          L.polyline(track, {
            color: color,
            weight: 2,
            dashArray: '5, 10',
          }).addTo(map);
        }
      });

      if (showTerrain) {
        L.rectangle(
          [[39.85, 116.35], [39.95, 116.45]],
          { color: '#faad14', fillOpacity: 0.1, weight: 2 }
        )
          .bindPopup('地形: 丘陵地带')
          .addTo(map);
      }
    };

    drawMap();
  }, [units, showTerrain, showWeather, showTracks]);

  return (
    <Card
      title="态势地图"
      extra={
        <Space>
          <Checkbox checked={showTerrain} onChange={(e) => onToggleLayer?.('terrain', e.target.checked)}>
            地形
          </Checkbox>
          <Checkbox checked={showWeather} onChange={(e) => onToggleLayer?.('weather', e.target.checked)}>
            气象
          </Checkbox>
          <Checkbox checked={showTracks} onChange={(e) => onToggleLayer?.('tracks', e.target.checked)}>
            轨迹
          </Checkbox>
        </Space>
      }
      style={{ borderRadius: 8 }}
    >
      <div
        ref={mapRef}
        id="map"
        style={{
          width: '100%',
          height: 600,
          borderRadius: 4,
          overflow: 'hidden',
        }}
      />
    </Card>
  );
}
