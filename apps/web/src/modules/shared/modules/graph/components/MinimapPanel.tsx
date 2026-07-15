/**
 * MinimapPanel — Sigma.js 图谱缩略图面板
 *
 * 优先使用 @react-sigma/minimap 原生组件（WebGL 渲染，视口矩形精确）
 * 降级到 Canvas 手绘版（当 SigmaProvider 上下文不可用时）
 */
import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { MiniMap } from '@react-sigma/minimap';
import { SigmaProvider } from '@react-sigma/core';
import type Sigma from 'sigma';
import type Graph from 'graphology';

export interface MinimapPanelProps {
  /** 是否显示 */
  visible: boolean;
  /** Sigma 实例 ref（通过 .current 取值，保证实时性） */
  sigmaRef?: React.RefObject<Sigma | null>;
  /** Graphology 实例 ref（通过 .current 取值，保证实时性） */
  graphRef?: React.RefObject<Graph | null>;
  /** 画布宽度（px） */
  width?: number;
  /** 画布高度（px） */
  height?: number;
}

const DEFAULT_WIDTH = 200;
const DEFAULT_HEIGHT = 200;

// ═══════════════════════════════════════════════
// 原生 MiniMap 版（@react-sigma/minimap）
// ═══════════════════════════════════════════════

interface NativeMinimapProps {
  sigma: Sigma;
  width: number;
  height: number;
}

function NativeMinimap({ sigma, width, height }: NativeMinimapProps) {
  // 从已有 sigma 实例构造上下文值
  const contextValue = useMemo(
    () => ({ sigma, container: sigma.getContainer() }),
    [sigma],
  );

  return (
    <SigmaProvider value={contextValue}>
      <div
        className="graph-minimap-panel"
        style={{
          background: 'rgba(255,255,255,0.72)',
          backdropFilter: 'blur(6px)',
          borderRadius: '0 8px 8px 0',
          boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
          overflow: 'hidden',
          borderLeft: '2px solid rgba(24, 144, 255, 0.3)',
        }}
      >
        <MiniMap
          width={`${width}px`}
          height={`${height}px`}
          debounceTime={50}
        />
      </div>
    </SigmaProvider>
  );
}

// ═══════════════════════════════════════════════
// Canvas 手绘降级版
// ═══════════════════════════════════════════════

interface CanvasMinimapProps {
  sigmaRef?: React.RefObject<Sigma | null>;
  graphRef?: React.RefObject<Graph | null>;
  width: number;
  height: number;
}

function CanvasMinimap({ sigmaRef, graphRef, width, height }: CanvasMinimapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const graph = graphRef?.current;
    const sigma = sigmaRef?.current;

    if (!canvas || !graph || graph.order === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(245, 247, 250, 0.95)';
    ctx.fillRect(0, 0, w, h);

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    graph.forEachNode((_node, attrs) => {
      const x = attrs.x as number ?? 0;
      const y = attrs.y as number ?? 0;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    });

    const padFactor = 0.08;
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    minX -= rangeX * padFactor; maxX += rangeX * padFactor;
    minY -= rangeY * padFactor; maxY += rangeY * padFactor;

    const scaleX = w / (maxX - minX);
    const scaleY = h / (maxY - minY);
    const scale = Math.min(scaleX, scaleY);
    const offsetX = (w - (maxX - minX) * scale) / 2;
    const offsetY = (h - (maxY - minY) * scale) / 2;
    const toPixelX = (gx: number) => (gx - minX) * scale + offsetX;
    const toPixelY = (gy: number) => (gy - minY) * scale + offsetY;

    ctx.strokeStyle = 'rgba(180, 180, 180, 0.3)';
    ctx.lineWidth = 0.5;
    graph.forEachEdge((_edge, _attrs, source, target) => {
      if (!graph.hasNode(source) || !graph.hasNode(target)) return;
      const sAttrs = graph.getNodeAttributes(source);
      const tAttrs = graph.getNodeAttributes(target);
      ctx.beginPath();
      ctx.moveTo(toPixelX(sAttrs.x as number), toPixelY(sAttrs.y as number));
      ctx.lineTo(toPixelX(tAttrs.x as number), toPixelY(tAttrs.y as number));
      ctx.stroke();
    });

    graph.forEachNode((_node, attrs) => {
      const x = toPixelX(attrs.x as number);
      const y = toPixelY(attrs.y as number);
      const color = (attrs.color as string) || '#999';
      ctx.beginPath();
      ctx.arc(x, y, 2.5, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
    });

    if (sigma) {
      try {
        const vr = sigma.viewRectangle();
        const vpMinX = toPixelX(vr.x1);
        const vpMinY = toPixelY(vr.y1);
        const vpMaxX = toPixelX(vr.x2);
        const vpMaxY = toPixelY(vr.y2);
        ctx.fillStyle = 'rgba(24, 144, 255, 0.06)';
        ctx.fillRect(vpMinX, vpMinY, vpMaxX - vpMinX, vpMaxY - vpMinY);
        ctx.strokeStyle = 'rgba(24, 144, 255, 0.8)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(vpMinX, vpMinY, vpMaxX - vpMinX, vpMaxY - vpMinY);
      } catch { /* sigma not ready */ }
    }
  }, [sigmaRef, graphRef]);

  useEffect(() => {
    if (!sigmaRef?.current) return;
    const camera = sigmaRef.current.getCamera();
    const scheduleRedraw = () => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(draw);
    };
    camera.on('updated', scheduleRedraw);
    draw();
    return () => {
      camera.removeListener('updated', scheduleRedraw);
      cancelAnimationFrame(rafRef.current);
    };
  }, [sigmaRef, graphRef, draw]);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [draw]);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const sigma = sigmaRef?.current;
    const graph = graphRef?.current;
    if (!sigma || !graph || graph.order === 0) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    graph.forEachNode((_node, attrs) => {
      const x = attrs.x as number ?? 0;
      const y = attrs.y as number ?? 0;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    });

    const padFactor = 0.08;
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    minX -= rangeX * padFactor; maxX += rangeX * padFactor;
    minY -= rangeY * padFactor; maxY += rangeY * padFactor;

    const sX = canvas.width / (maxX - minX);
    const sY = canvas.height / (maxY - minY);
    const scale = Math.min(sX, sY);
    const offsetX = (canvas.width - (maxX - minX) * scale) / 2;
    const offsetY = (canvas.height - (maxY - minY) * scale) / 2;

    const graphX = (clickX - offsetX) / scale + minX;
    const graphY = (clickY - offsetY) / scale + minY;

    sigma.getCamera().animate({ x: graphX, y: graphY }, { duration: 300 });
  }, [sigmaRef, graphRef]);

  return (
    <div
      className="graph-minimap-panel"
      style={{
        background: 'rgba(255,255,255,0.72)',
        backdropFilter: 'blur(6px)',
        borderRadius: '0 8px 8px 0',
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
        overflow: 'hidden',
        borderLeft: '2px solid rgba(24, 144, 255, 0.3)',
      }}
    >
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        onClick={handleClick}
        style={{ display: 'block', cursor: 'pointer' }}
      />
    </div>
  );
}

// ═══════════════════════════════════════════════
// 主组件：自动选择原生 or 降级
// ═══════════════════════════════════════════════

export function MinimapPanel({
  visible,
  sigmaRef,
  graphRef,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
}: MinimapPanelProps) {
  // 延迟读取 sigma 实例（ref 值在 useEffect 中赋值）
  const [sigmaInstance, setSigmaInstance] = useState<Sigma | null>(null);

  useEffect(() => {
    if (!visible) return;
    // 立即尝试读取，如果已有则设置
    const sigma = sigmaRef?.current ?? null;
    if (sigma) {
      setSigmaInstance(sigma);
      return;
    }
    // 如果还没创建，轮询等待（最多 2 秒）
    let frame = 0;
    const maxFrames = 60;
    const poll = () => {
      const s = sigmaRef?.current ?? null;
      if (s) {
        setSigmaInstance(s);
        return;
      }
      frame++;
      if (frame < maxFrames) {
        requestAnimationFrame(poll);
      }
    };
    const raf = requestAnimationFrame(poll);
    return () => cancelAnimationFrame(raf);
  }, [visible, sigmaRef]);

  if (!visible) return null;

  // 优先使用原生 MiniMap（WebGL 渲染，视口矩形精确）
  if (sigmaInstance) {
    return <NativeMinimap sigma={sigmaInstance} width={width} height={height} />;
  }

  // 降级：Canvas 手绘版（sigma 实例不可用或 SigmaProvider 上下文缺失时）
  return (
    <CanvasMinimap
      sigmaRef={sigmaRef}
      graphRef={graphRef}
      width={width}
      height={height}
    />
  );
}
