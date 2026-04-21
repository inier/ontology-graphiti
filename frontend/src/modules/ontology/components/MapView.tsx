import { useState, useRef, useEffect } from 'react';
import type { MapUnit } from '../../shared/types';

interface MapViewProps {
  units: MapUnit[];
}

export function MapView({ units }: MapViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  useEffect(() => {
    drawMap();
  }, [units, scale, offset]);

  const drawMap = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 绘制网格
    ctx.strokeStyle = '#e8e8e8';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 50) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 50) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // 绘制单位
    units.forEach((unit) => {
      const x = unit.position[0] * scale + offset.x;
      const y = unit.position[1] * scale + offset.y;

      // 绘制单位图标
      ctx.beginPath();
      ctx.arc(x, y, 15 * scale, 0, Math.PI * 2);
      ctx.fillStyle = unit.side === 'blue' ? '#1890ff' : unit.side === 'red' ? '#ff4d4f' : '#52c41a';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // 绘制单位名称
      ctx.fillStyle = '#000000';
      ctx.font = `${12 * scale}px Arial`;
      ctx.textAlign = 'center';
      ctx.fillText(unit.name, x, y - 25 * scale);

      // 绘制单位状态
      ctx.fillStyle = unit.status === 'active' ? '#52c41a' : unit.status === 'moving' ? '#faad14' : '#8c8c8c';
      ctx.beginPath();
      ctx.arc(x, y + 20 * scale, 5 * scale, 0, Math.PI * 2);
      ctx.fill();
    });
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale((prev) => Math.max(0.5, Math.min(3, prev * delta)));
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isDragging) {
      setOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        overflow: 'hidden',
        cursor: isDragging ? 'grabbing' : 'grab',
      }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
        }}
      />
      <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(255, 255, 255, 0.8)', padding: 8, borderRadius: 4 }}>
        <div>缩放: {Math.round(scale * 100)}%</div>
        <div>单位数量: {units.length}</div>
      </div>
    </div>
  );
}