import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Card, Empty, Space, Tag } from 'antd';
import { Graph } from '@antv/g6';
import { GraphToolbar } from './GraphToolbar';
import { GraphControls } from './GraphControls';
import {
  getNodeColor, getNodeShape, getEdgeStyle, getSideColor,
  ZOOM_STEP, ZOOM_MIN, ZOOM_MAX,
  LOD_LABEL_THRESHOLD, LOD_EDGE_LABEL_THRESHOLD, LOD_BIG_GRAPH_THRESHOLD,
  LAYOUT_MAX_ITERATIONS, LAYOUT_CANVAS_SIZE, LAYOUT_CENTER,
  MINIMAP_MAX_SIZE,
} from './constants';
import type { LayoutType } from './constants';

const AUDIT_KEYWORDS = new Set(['AuditLog', 'AuditUser', 'AuditResource', 'AuditService']);
function isAuditType(t: string) { return AUDIT_KEYWORDS.has(t); }

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  side?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
}

interface GraphCanvasProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  onRefresh?: () => void;
  versions?: Array<{
    version_id: string;
    created_at: string;
    entity_count: number;
    relation_count: number;
    commit_message?: string;
    event_count?: number;
  }>;
  currentVersion?: string;
  onVersionChange?: (versionId: string) => void;
  versionsLoading?: boolean;
}

export function GraphCanvas({ nodes, edges, onNodeClick, onEdgeClick, onRefresh, versions, currentVersion, onVersionChange, versionsLoading }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const [layout, setLayout] = useState<LayoutType>('force');
  const [searchText, setSearchText] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [layoutReady, setLayoutReady] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);
  const zoomLevelRef = useRef(1);
  const [canvasHeight, setCanvasHeight] = useState(() =>
    typeof window !== 'undefined' ? window.innerHeight - 200 : 700
  );

  const setZoomLevelStable = useCallback((val: number) => {
    const rounded = Math.round(val * 100) / 100;
    if (Math.abs(rounded - zoomLevelRef.current) > 0.005) {
      zoomLevelRef.current = rounded;
      setZoomLevel(rounded);
    }
  }, []);

  const [showAudit, setShowAudit] = useState(false);

  const selectedNodeIdRef = useRef<string | null>(null);
  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;
  const onEdgeClickRef = useRef(onEdgeClick);
  onEdgeClickRef.current = onEdgeClick;

  const entityTypes = useMemo(() => {
    const typeSet = new Set<string>();
    nodes.forEach((n) => typeSet.add(n.type));
    return Array.from(typeSet).sort();
  }, [nodes]);

  const filteredNodes = useMemo(() => {
    let result = nodes;
    if (!showAudit) {
      result = result.filter((n) => !isAuditType(n.type));
    }
    if (filterType !== 'all') {
      result = result.filter((n) => n.type === filterType);
    }
    return result;
  }, [nodes, filterType, showAudit]);

  const filteredEdges = useMemo(() => {
    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    return edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));
  }, [edges, filteredNodes]);

  const isLargeGraph = filteredNodes.length > LOD_BIG_GRAPH_THRESHOLD;

  const filterKey = useMemo(() =>
    `${filterType}|${showAudit}|${filteredNodes.map((n) => n.id).sort().join(',')}`,
    [filterType, showAudit, filteredNodes],
  );

  const buildGraphData = useCallback(() => ({
    nodes: filteredNodes.map((n) => ({
      id: n.id,
      data: { label: n.name, nodeType: n.type, side: n.side },
    })),
    edges: filteredEdges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      data: { edgeType: e.type, label: e.type },
    })),
  }), [filteredNodes, filteredEdges]);

  const getLayoutConfig = useCallback((layoutType: string) => {
    const base = {
      width: LAYOUT_CANVAS_SIZE,
      height: LAYOUT_CANVAS_SIZE,
      center: LAYOUT_CENTER as [number, number],
      animate: false,
    };
    switch (layoutType) {
      case 'force':
        return {
          ...base,
          type: 'force',
          preventOverlap: true,
          nodeSize: 60,
          nodeSpacing: 40,
          nodeStrength: -300,
          linkDistance: 180,
          edgeStrength: 0.1,
          collideStrength: 1,
          alphaDecay: 0.028,
          alphaMin: 0.001,
          maxIterations: 500,
        };
      case 'circular':
        return {
          ...base,
          type: 'circular',
          preventOverlap: true,
          nodeSize: 60,
          nodeSpacing: 40,
        };
      case 'grid':
        return {
          ...base,
          type: 'grid',
          preventOverlap: true,
          nodeSize: 60,
          nodeSpacing: 40,
        };
      case 'dagre':
        return {
          ...base,
          type: 'dagre',
          preventOverlap: true,
          nodeSize: 60,
          nodeSpacing: 40,
          ranksep: 60,
          nodesep: 40,
        };
      case 'radial':
        return {
          ...base,
          type: 'radial',
          preventOverlap: true,
          nodeSize: 60,
          nodeSpacing: 40,
          nodeStrength: -300,
          linkDistance: 180,
          collideStrength: 1,
        };
      default:
        return { ...base, type: layoutType, preventOverlap: true, nodeSize: 60 };
    }
  }, []);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const updateHeight = () => {
      const rect = wrapper.getBoundingClientRect();
      const top = rect.top;
      const available = window.innerHeight - top - 16 * 2 - 64 - 8;
      setCanvasHeight(Math.max(400, available));
    };
    updateHeight();
    const ro = new ResizeObserver(updateHeight);
    ro.observe(wrapper);
    window.addEventListener('resize', updateHeight);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', updateHeight);
    };
  }, []);

  const updateZoomState = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;
    try {
      const gc = graph.getCanvas?.();
      const camera = gc?.getCamera?.() || (gc as any)?.camera;
      const z = camera?.getZoom?.() ?? graphRef.current?.getZoom?.();
      if (typeof z === 'number') setZoomLevelStable(z);
    } catch (_) {}
  }, [setZoomLevelStable]);

  const handleZoomIn = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;
    try {
      const current = graph.getZoom?.() || 1;
      const target = Math.min(current + ZOOM_STEP, ZOOM_MAX);
      graph.zoomTo?.(target);
      setZoomLevelStable(target);
      [50, 150, 300, 500].forEach(delay => {
        setTimeout(() => {
          trackViewportRef.current?.(graph);
          drawMinimapRef.current?.();
        }, delay);
      });
    } catch (_) {}
  }, [setZoomLevelStable]);

  const handleZoomOut = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;
    try {
      const current = graph.getZoom?.() || 1;
      const target = Math.max(current - ZOOM_STEP, ZOOM_MIN);
      graph.zoomTo?.(target);
      setZoomLevelStable(target);
      [50, 150, 300, 500].forEach(delay => {
        setTimeout(() => {
          trackViewportRef.current?.(graph);
          drawMinimapRef.current?.();
        }, delay);
      });
    } catch (_) {}
  }, [setZoomLevelStable]);

  const handleFitView = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;
    try {
      graphRef.current?.fitView?.();
      setTimeout(() => updateZoomState(), 400);
    } catch (_) {}
  }, [updateZoomState]);

  const handleZoomReset = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;
    try {
      graph.zoomTo?.(1);
      setZoomLevelStable(1);
      setTimeout(() => {
        trackViewportRef.current?.(graph);
        drawMinimapRef.current?.();
      }, 100);
    } catch (_) { }
  }, [setZoomLevelStable]);

  const handleCenterView = useCallback(() => {
    const graph = graphRef.current;
    if (!graph) return;
    try {
      graph.fitCenter?.();
      setTimeout(() => {
        updateZoomState();
        const g = graphRef.current;
        if (g) trackViewportRef.current?.(g);
        drawMinimapRef.current?.();
      }, 200);
    } catch (_) { }
  }, [updateZoomState]);

  // --- LOD refs ---
  const labelVisibleRef = useRef(!isLargeGraph);
  const edgeLabelVisibleRef = useRef(false);
  const lodDrawTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleLODDraw = useCallback((graph: Graph) => {
    if (lodDrawTimerRef.current) clearTimeout(lodDrawTimerRef.current);
    lodDrawTimerRef.current = setTimeout(() => {
      lodDrawTimerRef.current = null;
      try { graph.draw?.(); } catch (_) {}
    }, 120);
  }, []);

  // --- Minimap ---
  const minimapCanvasRef = useRef<HTMLCanvasElement>(null);
  const minimapDragging = useRef(false);
  const minimapDragStart = useRef({ clientX: 0, clientY: 0, worldX: 0, worldY: 0, blueBoxX: 0, blueBoxY: 0, blueBoxW: 0, blueBoxH: 0 });
  const minimapSizeRef = useRef({ w: 200, h: 150 });
  const minimapBlueBoxRef = useRef({ x: 0, y: 0, w: 0, h: 0 });
  const [minimapOpen, setMinimapOpen] = useState(false);
  const minimapOpenRef = useRef(false);
  const viewportRef = useRef({ x: 0, y: 0, width: 0, height: 0, zoom: 1 });
  const graphBoundsRef = useRef({ minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0 });

  // 缩略图尺寸与图谱显示窗口等比例
  const containerW = containerRef.current?.clientWidth || 800;
  const containerH = containerRef.current?.clientHeight || 600;
  const containerRatio = containerW / containerH;
  let MINIMAP_WIDTH: number;
  let MINIMAP_HEIGHT: number;
  if (containerRatio >= 1) {
    MINIMAP_WIDTH = MINIMAP_MAX_SIZE;
    MINIMAP_HEIGHT = Math.round(MINIMAP_MAX_SIZE / containerRatio);
  } else {
    MINIMAP_HEIGHT = MINIMAP_MAX_SIZE;
    MINIMAP_WIDTH = Math.round(MINIMAP_MAX_SIZE * containerRatio);
  }
  minimapSizeRef.current = { w: MINIMAP_WIDTH, h: MINIMAP_HEIGHT };

  useEffect(() => {
    minimapOpenRef.current = minimapOpen;
  }, [minimapOpen]);

  const updateGraphBounds = useCallback((graph: Graph) => {
    try {
      let minX = Infinity, maxX = -Infinity;
      let minY = Infinity, maxY = -Infinity;
      let hasPosition = false;

      for (const node of filteredNodes) {
        try {
          const pos = graph.getElementPosition?.(node.id);
          if (pos) {
            const px = Array.isArray(pos) ? pos[0] : (pos as any).x;
            const py = Array.isArray(pos) ? pos[1] : (pos as any).y;
            if (typeof px === 'number' && typeof py === 'number') {
              minX = Math.min(minX, px);
              maxX = Math.max(maxX, px);
              minY = Math.min(minY, py);
              maxY = Math.max(maxY, py);
              hasPosition = true;
            }
          }
        } catch (_) {}
      }

      if (hasPosition) {
        const padding = 150;
        graphBoundsRef.current = {
          minX: minX - padding,
          maxX: maxX + padding,
          minY: minY - padding,
          maxY: maxY + padding,
          width: maxX - minX + 2 * padding,
          height: maxY - minY + 2 * padding,
        };
      } else {
        const half = LAYOUT_CANVAS_SIZE / 2;
        graphBoundsRef.current = {
          minX: -half, maxX: half, minY: -half, maxY: half,
          width: LAYOUT_CANVAS_SIZE, height: LAYOUT_CANVAS_SIZE,
        };
      }
    } catch (_) {
      const half = LAYOUT_CANVAS_SIZE / 2;
      graphBoundsRef.current = {
        minX: -half, maxX: half, minY: -half, maxY: half,
        width: LAYOUT_CANVAS_SIZE, height: LAYOUT_CANVAS_SIZE,
      };
    }
  }, [filteredNodes]);

  const computeMinimapLayout = useCallback((
    nodeList: typeof filteredNodes,
  ) => {
    const items: Array<{ id: string; x: number; y: number; type: string }> = [];
    const count = nodeList.length;
    if (count === 0) return items;

    const graph = graphRef.current;
    const bounds = graphBoundsRef.current;

    // 尝试从图谱获取节点实际位置
    const posMap = new Map<string, { x: number; y: number }>();
    let hasRealPositions = false;
    if (graph) {
      for (const node of nodeList) {
        try {
          const pos = graph.getElementPosition?.(node.id);
          if (pos) {
            const px = Array.isArray(pos) ? pos[0] : (pos as any).x;
            const py = Array.isArray(pos) ? pos[1] : (pos as any).y;
            if (typeof px === 'number' && typeof py === 'number') {
              posMap.set(node.id, { x: px, y: py });
              hasRealPositions = true;
            }
          }
        } catch (_) {}
      }
    }

    if (hasRealPositions && bounds.width > 0 && bounds.height > 0) {
      // 使用实际位置映射到 minimap
      const scaleX = MINIMAP_WIDTH / bounds.width;
      const scaleY = MINIMAP_HEIGHT / bounds.height;
      const scale = Math.min(scaleX, scaleY);
      const offsetX = (MINIMAP_WIDTH - bounds.width * scale) / 2;
      const offsetY = (MINIMAP_HEIGHT - bounds.height * scale) / 2;

      for (const node of nodeList) {
        const pos = posMap.get(node.id);
        if (pos) {
          items.push({
            id: node.id,
            x: (pos.x - bounds.minX) * scale + offsetX,
            y: (pos.y - bounds.minY) * scale + offsetY,
            type: node.type,
          });
        } else {
          items.push({
            id: node.id,
            x: MINIMAP_WIDTH / 2,
            y: MINIMAP_HEIGHT / 2,
            type: node.type,
          });
        }
      }
    } else {
      // 降级：使用环形布局
      const maxRadius = Math.min(MINIMAP_WIDTH, MINIMAP_HEIGHT) * 0.42;
      const layers = Math.ceil(Math.sqrt(count));
      let idx = 0;
      for (let layer = 0; layer < layers && idx < count; layer++) {
        const radius = ((layer + 1) / layers) * maxRadius;
        const nodesInLayer = layer === layers - 1 ? count - idx : Math.ceil(count / layers);
        for (let j = 0; j < nodesInLayer && idx < count; j++) {
          const angle = (2 * Math.PI * j) / nodesInLayer - Math.PI / 2;
          items.push({
            id: nodeList[idx].id,
            x: MINIMAP_WIDTH / 2 + radius * Math.cos(angle),
            y: MINIMAP_HEIGHT / 2 + radius * Math.sin(angle),
            type: nodeList[idx].type,
          });
          idx++;
        }
      }
    }
    return items;
  }, [MINIMAP_WIDTH, MINIMAP_HEIGHT, filteredNodes]);

  const drawMinimap = useCallback((forcedBlueBox?: { x: number; y: number; w: number; h: number } | null) => {
    const canvas = minimapCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { w, h } = minimapSizeRef.current;
    canvas.width = w * devicePixelRatio;
    canvas.height = h * devicePixelRatio;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(devicePixelRatio, devicePixelRatio);

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(255,255,255,0.75)';
    ctx.fillRect(0, 0, w, h);

    const layoutNodes = computeMinimapLayout(filteredNodes);

    try {
      if (layoutNodes.length > 0) {
        const posMap = new Map<string, { x: number; y: number }>();
        for (const n of layoutNodes) posMap.set(n.id, { x: n.x, y: n.y });

        ctx.strokeStyle = 'rgba(150,150,150,0.35)';
        ctx.lineWidth = 0.5;
        for (const ed of filteredEdges) {
          const src = posMap.get(ed.source);
          const tgt = posMap.get(ed.target);
          if (src && tgt) {
            ctx.beginPath();
            ctx.moveTo(src.x, src.y);
            ctx.lineTo(tgt.x, tgt.y);
            ctx.stroke();
          }
        }

        for (const n of layoutNodes) {
          ctx.fillStyle = getNodeColor(n.type);
          ctx.beginPath();
          ctx.arc(n.x, n.y, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    } catch (_) {}

    const bounds = graphBoundsRef.current;
    if (layoutNodes.length > 0 && bounds.width > 0 && bounds.height > 0) {
      const el = containerRef.current;
      const vw = el?.clientWidth || 800;
      const vh = el?.clientHeight || 600;

      const scaleX = w / bounds.width;
      const scaleY = h / bounds.height;
      const scale = Math.min(scaleX, scaleY);
      const offsetX = (w - bounds.width * scale) / 2;
      const offsetY = (h - bounds.height * scale) / 2;

      let visLeft = 0, visTop = 0, visW = vw, visH = vh;
      let currentZoom = 1;

      const graph = graphRef.current;
      if (graph) {
        try {
          if (graph.getCanvasByViewport) {
            const tl = graph.getCanvasByViewport([0, 0]);
            const br = graph.getCanvasByViewport([vw, vh]);
            if (tl && br) {
              const tlX = Array.isArray(tl) ? tl[0] : (tl as any).x;
              const tlY = Array.isArray(tl) ? tl[1] : (tl as any).y;
              const brX = Array.isArray(br) ? br[0] : (br as any).x;
              const brY = Array.isArray(br) ? br[1] : (br as any).y;
              visLeft = tlX;
              visTop = tlY;
              visW = brX - tlX;
              visH = brY - tlY;
              currentZoom = visW > 0 ? vw / visW : 1;
            }
          } else {
            currentZoom = graph.getZoom?.() ?? 1;
            visW = vw / currentZoom;
            visH = vh / currentZoom;
            const pos = graph.getPosition?.();
            if (pos) {
              const posX = Array.isArray(pos) ? pos[0] : (pos as any).x ?? 0;
              const posY = Array.isArray(pos) ? pos[1] : (pos as any).y ?? 0;
              visLeft = -posX / currentZoom;
              visTop = -posY / currentZoom;
            } else {
              visLeft = -visW / 2;
              visTop = -visH / 2;
            }
          }
        } catch (_) {
          currentZoom = graph.getZoom?.() ?? 1;
          visW = vw / currentZoom;
          visH = vh / currentZoom;
          visLeft = -visW / 2;
          visTop = -visH / 2;
        }
      } else {
        const vp = viewportRef.current;
        currentZoom = vp.zoom > 0 ? vp.zoom : 1;
        visLeft = vp.x - vw / (2 * currentZoom);
        visTop = vp.y - vh / (2 * currentZoom);
        visW = vw / currentZoom;
        visH = vh / currentZoom;
      }

      let boxW: number, boxH: number;

      if (forcedBlueBox) {
        boxW = Math.min(forcedBlueBox.w, w);
        boxH = Math.min(forcedBlueBox.h, h);
        const clampedX = Math.max(0, Math.min(forcedBlueBox.x, w - boxW));
        const clampedY = Math.max(0, Math.min(forcedBlueBox.y, h - boxH));

        minimapBlueBoxRef.current = { x: clampedX, y: clampedY, w: boxW, h: boxH };

        ctx.fillStyle = 'rgba(24,144,255,0.12)';
        ctx.fillRect(clampedX, clampedY, boxW, boxH);
        ctx.strokeStyle = '#1890ff';
        ctx.lineWidth = 2;
        ctx.strokeRect(clampedX, clampedY, boxW, boxH);
      } else {
        const vx = (visLeft - bounds.minX) * scale + offsetX;
        const vy = (visTop - bounds.minY) * scale + offsetY;
        boxW = Math.min(Math.max(visW * scale, 8), w);
        boxH = Math.min(Math.max(visH * scale, 6), h);

        const clampedX = Math.max(0, Math.min(vx, w - boxW));
        const clampedY = Math.max(0, Math.min(vy, h - boxH));

        minimapBlueBoxRef.current = { x: clampedX, y: clampedY, w: boxW, h: boxH };

        ctx.fillStyle = 'rgba(24,144,255,0.12)';
        ctx.fillRect(clampedX, clampedY, boxW, boxH);
        ctx.strokeStyle = '#1890ff';
        ctx.lineWidth = 2;
        ctx.strokeRect(clampedX, clampedY, boxW, boxH);
      }

      ctx.fillStyle = '#999';
      ctx.font = '9px monospace';
      ctx.fillText(`z:${currentZoom.toFixed(2)} box:${Math.round(boxW)}x${Math.round(boxH)}`, 2, h - 3);
    }
  }, [filteredNodes, filteredEdges, computeMinimapLayout]);

  const drawMinimapRef = useRef(drawMinimap);
  drawMinimapRef.current = drawMinimap;

  const screenToWorld = useCallback((clientX: number, clientY: number) => {
    const canvas = minimapCanvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const bounds = graphBoundsRef.current;
    const { w, h } = minimapSizeRef.current;
    if (bounds.width <= 0 || bounds.height <= 0) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    const scaleX = w / bounds.width;
    const scaleY = h / bounds.height;
    const scale = Math.min(scaleX, scaleY);
    const offsetX = (w - bounds.width * scale) / 2;
    const offsetY = (h - bounds.height * scale) / 2;
    return {
      x: (mx - offsetX) / scale + bounds.minX,
      y: (my - offsetY) / scale + bounds.minY,
    };
  }, []);

  const handleMinimapMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const canvas = minimapCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const blueBox = minimapBlueBoxRef.current;
    const onBlueBox = blueBox.w > 0 && blueBox.h > 0 &&
      mx >= blueBox.x && mx <= blueBox.x + blueBox.w &&
      my >= blueBox.y && my <= blueBox.y + blueBox.h;

    if (onBlueBox) {
      minimapDragStart.current = {
        clientX: e.clientX,
        clientY: e.clientY,
        worldX: 0,
        worldY: 0,
        blueBoxX: blueBox.x,
        blueBoxY: blueBox.y,
        blueBoxW: blueBox.w,
        blueBoxH: blueBox.h,
      };
      minimapDragging.current = true;
    } else {
      const bounds = graphBoundsRef.current;
      if (bounds.width <= 0 || bounds.height <= 0) return;
      const world = screenToWorld(e.clientX, e.clientY);
      const graph = graphRef.current;
      if (!graph) return;
      const el = containerRef.current;
      const vw = el?.clientWidth || 800;
      const vh = el?.clientHeight || 600;
      try {
        let effectiveZoom = graph.getZoom?.() ?? 1;
        if (graph.getCanvasByViewport) {
          const tl = graph.getCanvasByViewport([0, 0]);
          const br = graph.getCanvasByViewport([vw, 0]);
          if (tl && br) {
            const tlX = Array.isArray(tl) ? tl[0] : (tl as any).x;
            const brX = Array.isArray(br) ? br[0] : (br as any).x;
            const visW = brX - tlX;
            if (visW > 0) effectiveZoom = vw / visW;
          }
        }
        const tx = vw / 2 - world.x * effectiveZoom;
        const ty = vh / 2 - world.y * effectiveZoom;
        graph.translateTo?.([tx, ty]);
      } catch (_) {}
      setTimeout(() => drawMinimapRef.current?.(), 50);
    }
  }, [screenToWorld]);

  const handleMinimapMouseMove = useCallback((e: React.MouseEvent | MouseEvent) => {
    if (!minimapDragging.current) return;
    const rawEvent = 'nativeEvent' in e ? (e as React.MouseEvent).nativeEvent : (e as MouseEvent);
    rawEvent.preventDefault?.();
    const start = minimapDragStart.current;
    const bounds = graphBoundsRef.current;
    const { w, h } = minimapSizeRef.current;
    if (bounds.width <= 0 || bounds.height <= 0) return;

    const pixelDx = e.clientX - start.clientX;
    const pixelDy = e.clientY - start.clientY;

    const newBlueX = start.blueBoxX + pixelDx;
    const newBlueY = start.blueBoxY + pixelDy;
    const boxW = start.blueBoxW;
    const boxH = start.blueBoxH;
    const clampedX = Math.max(0, Math.min(newBlueX, w - boxW));
    const clampedY = Math.max(0, Math.min(newBlueY, h - boxH));

    drawMinimapRef.current?.({ x: clampedX, y: clampedY, w: boxW, h: boxH });

    const scaleX = w / bounds.width;
    const scaleY = h / bounds.height;
    const scale = Math.min(scaleX, scaleY);
    const offsetX = (w - bounds.width * scale) / 2;
    const offsetY = (h - bounds.height * scale) / 2;

    const blueCenterX = clampedX + boxW / 2;
    const blueCenterY = clampedY + boxH / 2;
    const worldX = (blueCenterX - offsetX) / scale + bounds.minX;
    const worldY = (blueCenterY - offsetY) / scale + bounds.minY;

    const graph = graphRef.current;
    if (graph) {
      const el = containerRef.current;
      const vw = el?.clientWidth || 800;
      const vh = el?.clientHeight || 600;
      try {
        let effectiveZoom = graph.getZoom?.() ?? 1;
        if (graph.getCanvasByViewport) {
          const tl = graph.getCanvasByViewport([0, 0]);
          const br = graph.getCanvasByViewport([vw, 0]);
          if (tl && br) {
            const tlX = Array.isArray(tl) ? tl[0] : (tl as any).x;
            const brX = Array.isArray(br) ? br[0] : (br as any).x;
            const visW = brX - tlX;
            if (visW > 0) effectiveZoom = vw / visW;
          }
        }
        const tx = vw / 2 - worldX * effectiveZoom;
        const ty = vh / 2 - worldY * effectiveZoom;
        graph.translateTo?.([tx, ty]);
      } catch (_) {}
    }
  }, []);

  const handleMinimapMouseUp = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    minimapDragging.current = false;
  }, []);

  const trackViewport = useCallback((g: Graph) => {
    try {
      const el = containerRef.current;
      const cw = el?.clientWidth || 800;
      const ch = el?.clientHeight || 600;
      let z = 1;

      const gc = g.getCanvas?.();
      if (gc) {
        const camera = gc.getCamera?.() || (gc as any).camera;
        if (camera) {
          z = camera.getZoom?.() ?? g.getZoom?.() ?? 1;

          let camX = 0, camY = 0;
          const pos = camera.getPosition?.();
          if (Array.isArray(pos) && pos.length >= 2) {
            camX = pos[0]; camY = pos[1];
          } else if (pos && typeof pos === 'object') {
            camX = (pos as any).x || 0; camY = (pos as any).y || 0;
          }

          const focalPoint = camera.getFocalPoint?.();
          if (focalPoint) {
            const fx = Array.isArray(focalPoint) ? focalPoint[0] : (focalPoint as any).x;
            const fy = Array.isArray(focalPoint) ? focalPoint[1] : (focalPoint as any).y;
            if (typeof fx === 'number' && typeof fy === 'number') {
              camX = fx; camY = fy;
            }
          }

          viewportRef.current = { x: camX, y: camY, width: cw, height: ch, zoom: z };
          return;
        }
      }

      try {
        z = g.getZoom?.() ?? 1;
      } catch (_) {}

      viewportRef.current = { x: 0, y: 0, width: cw, height: ch, zoom: z };
    } catch (_) {
      viewportRef.current = { x: 0, y: 0, width: 0, height: 0, zoom: 1 };
    }
  }, []);

  const trackViewportRef = useRef(trackViewport);
  trackViewportRef.current = trackViewport;

  const viewportChangeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleViewportChange = useCallback((graph: Graph) => {
    trackViewport(graph);
    if (minimapOpen) drawMinimapRef.current?.();

    if (viewportChangeTimerRef.current) clearTimeout(viewportChangeTimerRef.current);
    viewportChangeTimerRef.current = setTimeout(() => {
      viewportChangeTimerRef.current = null;
      updateZoomState();
      if (minimapOpen) drawMinimapRef.current?.();

      try {
        const z = graph.getZoom?.() || 1;
        const showLabels = z >= LOD_LABEL_THRESHOLD;
        const showEdgeLabels = z >= LOD_EDGE_LABEL_THRESHOLD;

        if (showLabels !== labelVisibleRef.current || showEdgeLabels !== edgeLabelVisibleRef.current) {
          labelVisibleRef.current = showLabels;
          edgeLabelVisibleRef.current = showEdgeLabels;
          scheduleLODDraw(graph);
        }
      } catch (_) {}
    }, 80);
  }, [updateZoomState, trackViewport, minimapOpen, scheduleLODDraw]);

  const handleViewportChangeRef = useRef(handleViewportChange);
  handleViewportChangeRef.current = handleViewportChange;

  useEffect(() => {
    let mounted = true;

    const createOrUpdateGraph = async () => {
      if (!containerRef.current || !mounted) return;

      const graphData = buildGraphData();

      const existingGraph = graphRef.current;
      if (existingGraph) {
        try {
          existingGraph.setData?.(graphData);
          await existingGraph.draw?.();
          if (mounted) {
            setLayoutReady(true);
            updateZoomState();
            labelVisibleRef.current = !isLargeGraph;
            edgeLabelVisibleRef.current = false;
          }
          return;
        } catch (e) {
          console.warn('增量更新失败，重建图谱:', e);
          try { existingGraph.destroy?.(); } catch (_) {}
          graphRef.current = null;
          selectedNodeIdRef.current = null;
        }
      }

      if (graphRef.current) {
        try { graphRef.current.destroy?.(); } catch (_) {}
        graphRef.current = null;
        selectedNodeIdRef.current = null;
      }

      labelVisibleRef.current = !isLargeGraph;
      edgeLabelVisibleRef.current = false;

      const graph = new Graph({
        container: containerRef.current,
        width: containerRef.current.clientWidth,
        height: canvasHeight,
        autoFit: 'center',
        padding: [40, 40, 40, 40],
        data: graphData,
        animation: false,
        zoomRange: [ZOOM_MIN, ZOOM_MAX],
        behaviors: [
          {
            type: 'drag-canvas',
            direction: 'both',
            sensitivity: 1,
            enableOptimize: true,
          },
          {
            type: 'zoom-canvas',
            sensitivity: 1,
            enableOptimize: true,
            zoomRange: [ZOOM_MIN, ZOOM_MAX],
            range: [ZOOM_MIN, ZOOM_MAX],
          },
          {
            type: 'drag-element',
            key: 'drag-element',
          },
          {
            type: 'hover-activate',
            key: 'hover-activate',
            degree: 1,
            inactiveState: 'dim',
            activeState: 'highlight',
          },
        ],
        node: {
          type: (d: any) => getNodeShape(d.data?.nodeType || ''),
          style: (d: any) => {
            const baseColor = getNodeColor(d.data?.nodeType || '');
            const side = d.data?.side;
            const strokeColor = getSideColor(side || 'neutral');
            const showLabel = labelVisibleRef.current;
            const size = 36;
            return {
              size,
              fill: baseColor,
              stroke: strokeColor,
              lineWidth: 2,
              labelText: showLabel ? (d.data?.label || d.id) : '',
              labelFill: '#333',
              labelFontSize: 11,
              labelPlacement: 'bottom',
              labelOffsetY: 8,
              labelBackground: true,
              labelBackgroundFill: '#fff',
              labelBackgroundOpacity: 0.6,
              labelBackgroundPadding: [2, 4],
            };
          },
          state: {
            selected: {
              stroke: '#ff4d4f',
              lineWidth: 3,
              labelFontSize: 13,
              labelFill: '#ff4d4f',
              labelFontWeight: 'bold',
              opacity: 1,
              size: 44,
              zIndex: 10,
            },
            highlight: {
              stroke: '#1890ff',
              lineWidth: 3,
              labelFontSize: 12,
              labelFill: '#1890ff',
              labelFontWeight: 'bold',
              opacity: 1,
              zIndex: 9,
            },
            dim: {
              opacity: 0.8,
              labelOpacity: 0.8,
            },
          },
        },
        edge: {
          type: 'line',
          style: (d: any) => {
            const base = getEdgeStyle(d.data?.edgeType || '');
            const showLabel = edgeLabelVisibleRef.current;
            return {
              ...base,
              endArrow: d.data?.edgeType !== 'located_at',
              labelText: showLabel ? (d.data?.label || '') : '',
              labelFontSize: 9,
              labelFill: '#8c8c8c',
              labelBackground: showLabel,
              labelBackgroundFill: '#fff',
              labelBackgroundOpacity: 0.7,
            };
          },
          state: {
            selected: { stroke: '#ff4d4f', lineWidth: 2 },
            highlight: {
              stroke: '#1890ff',
              lineWidth: 2,
              opacity: 1,
              labelFontSize: 11,
              labelFill: '#1890ff',
              labelFontWeight: 'bold',
              labelBackground: true,
              labelBackgroundFill: '#fff',
              labelBackgroundOpacity: 0.9,
              endArrow: true,
              zIndex: 9,
            },
            dim: {
              opacity: 0.8,
              labelOpacity: 0.8,
            },
          },
        },
        layout: getLayoutConfig(layout),
      });

      if (!mounted) {
        try { graph.destroy?.(); } catch (_) {}
        return;
      }

      try {
        await graph.render();
      } catch (e) {
        console.error('G6 渲染失败:', e);
        try { graph.destroy?.(); } catch (_) {}
        return;
      }

      if (!mounted) {
        try { graph.destroy?.(); } catch (_) {}
        return;
      }

      graph.on('node:click', (evt: any) => {
        if (!mounted) return;
        try {
          const nodeId = evt.target?.id;
          if (!nodeId) return;

          const prevSelected = selectedNodeIdRef.current;
          if (prevSelected === nodeId) {
            graph.setElementState({});
            selectedNodeIdRef.current = null;
            return;
          }

          const allEdges = graph.getEdgeData?.() || [];
          const relatedEdgeIds: string[] = [];
          const relatedNodeIds = new Set<string>([nodeId]);

          for (const edge of allEdges) {
            const src = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
            const tgt = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
            if (src === nodeId || tgt === nodeId) {
              relatedEdgeIds.push(edge.id!);
              if (src !== nodeId) relatedNodeIds.add(src);
              if (tgt !== nodeId) relatedNodeIds.add(tgt);
            }
          }

          const stateMap: Record<string, string | string[]> = {};

          const allNodeData = graph.getNodeData?.() || [];
          for (const nd of allNodeData) {
            if (nd.id === nodeId) {
              stateMap[nd.id!] = 'selected';
            } else if (relatedNodeIds.has(nd.id)) {
              stateMap[nd.id!] = 'highlight';
            } else {
              stateMap[nd.id!] = 'dim';
            }
          }

          for (const edge of allEdges) {
            if (relatedEdgeIds.includes(edge.id!)) {
              stateMap[edge.id!] = 'highlight';
            } else {
              stateMap[edge.id!] = 'dim';
            }
          }

          graph.setElementState(stateMap);
          selectedNodeIdRef.current = nodeId;

          const node = nodes.find((n) => n.id === nodeId);
          if (node) onNodeClickRef.current?.(node);
        } catch (e) {
          console.warn('节点点击事件处理错误:', e);
        }
      });

      graph.on('edge:click', (evt: any) => {
        if (!mounted) return;
        try {
          const edgeId = evt.target?.id;
          if (!edgeId) return;
          const edge = edges.find((e) => e.id === edgeId);
          if (edge) onEdgeClickRef.current?.(edge);
        } catch (e) {
          console.warn('边点击事件处理错误:', e);
        }
      });

      graph.on('canvas:click', () => {
        if (!mounted) return;
        try {
          const stateMap: Record<string, string | string[]> = {};
          const allNodeData = graph.getNodeData?.() || [];
          const allEdgeData = graph.getEdgeData?.() || [];
          for (const nd of allNodeData) stateMap[nd.id!] = [];
          for (const ed of allEdgeData) stateMap[ed.id!] = [];
          graph.setElementState(stateMap);
        } catch (_) {}
        selectedNodeIdRef.current = null;
      });

      graph.on('viewportchange', () => handleViewportChangeRef.current?.(graph));

      graph.on('node:dragend', () => {
        if (!mounted) return;
        updateGraphBounds(graph);
        if (minimapOpen) drawMinimap();
      });

      graphRef.current = graph;
      setLayoutReady(true);

      setTimeout(() => {
        if (mounted) {
          try { graph.fitView?.(); } catch (_) {}
          updateZoomState();
          trackViewport(graph);
          updateGraphBounds(graph);
          drawMinimap();
        }
      }, 400);
    };

    createOrUpdateGraph();

    return () => {
      mounted = false;
      if (lodDrawTimerRef.current) {
        clearTimeout(lodDrawTimerRef.current);
        lodDrawTimerRef.current = null;
      }
      if (graphRef.current) {
        try { graphRef.current.destroy?.(); } catch (_) {}
        graphRef.current = null;
      }
    };
  }, [filterKey, buildGraphData, canvasHeight]);

  // ===== Layout change =====
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !layoutReady) return;
    try {
      graph.setLayout?.(getLayoutConfig(layout));
      graph.layout?.();
      setTimeout(() => {
        try { graph.fitView?.(); } catch (_) {}
        updateZoomState();
        trackViewport(graph);
        updateGraphBounds(graph);
        if (minimapOpen) drawMinimapRef.current?.();
      }, 800);
    } catch (e) {
      console.warn('布局切换失败:', e);
    }
  }, [layout, layoutReady, getLayoutConfig, updateZoomState, updateGraphBounds, minimapOpen, trackViewport]);

  // ===== Search =====
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !layoutReady) return;
    try {
      if (searchText.trim()) {
        const keyword = searchText.trim().toLowerCase();
        let found = false;
        const allNodeData = graph.getNodeData?.();
        if (allNodeData) {
          for (const nd of allNodeData as any[]) {
            const label = ((nd.data?.label || nd.id || '') as string).toLowerCase();
            if (label.includes(keyword)) {
              const nodeId = nd.id;
              const allEdges = graph.getEdgeData?.() || [];
              const relatedEdgeIds: string[] = [];
              const relatedNodeIds = new Set<string>([nodeId]);

              for (const edge of allEdges) {
                const src = typeof edge.source === 'object' ? (edge.source as any).id : edge.source;
                const tgt = typeof edge.target === 'object' ? (edge.target as any).id : edge.target;
                if (src === nodeId || tgt === nodeId) {
                  relatedEdgeIds.push(edge.id!);
                  if (src !== nodeId) relatedNodeIds.add(src);
                  if (tgt !== nodeId) relatedNodeIds.add(tgt);
                }
              }

              const stateMap: Record<string, string | string[]> = {};
              for (const n of allNodeData as any[]) {
                if (n.id === nodeId) {
                  stateMap[n.id!] = 'selected';
                } else if (relatedNodeIds.has(n.id)) {
                  stateMap[n.id!] = 'highlight';
                } else {
                  stateMap[n.id!] = 'dim';
                }
              }
              for (const edge of allEdges) {
                if (relatedEdgeIds.includes(edge.id!)) {
                  stateMap[edge.id!] = 'highlight';
                } else {
                  stateMap[edge.id!] = 'dim';
                }
              }

              graph.setElementState(stateMap);
              graph.focusElement?.(nd.id!);
              selectedNodeIdRef.current = nodeId;
              found = true;
              break;
            }
          }
        }
        if (!found) {
          try {
            const stateMap: Record<string, string | string[]> = {};
            const allNodeData2 = graph.getNodeData?.() || [];
            const allEdgeData2 = graph.getEdgeData?.() || [];
            for (const nd of allNodeData2) stateMap[nd.id!] = [];
            for (const ed of allEdgeData2) stateMap[ed.id!] = [];
            graph.setElementState(stateMap);
          } catch (_) {}
        }
      } else {
        try {
          const stateMap: Record<string, string | string[]> = {};
          const allNodeData2 = graph.getNodeData?.() || [];
          const allEdgeData2 = graph.getEdgeData?.() || [];
          for (const nd of allNodeData2) stateMap[nd.id!] = [];
          for (const ed of allEdgeData2) stateMap[ed.id!] = [];
          graph.setElementState(stateMap);
        } catch (_) {}
        selectedNodeIdRef.current = null;
        handleFitView();
      }
    } catch (e) {
      console.warn('搜索定位失败:', e);
    }
  }, [searchText, layoutReady, handleFitView]);

  // ===== Global mouse events for minimap drag =====
  useEffect(() => {
    const handleGlobalMouseUp = () => { minimapDragging.current = false; };
    const handleGlobalMouseMove = (e: MouseEvent) => {
      if (!minimapDragging.current) return;
      e.preventDefault();
      handleMinimapMouseMove(e);
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    window.addEventListener('mousemove', handleGlobalMouseMove);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
      window.removeEventListener('mousemove', handleGlobalMouseMove);
    };
  }, [handleMinimapMouseMove]);

  // ===== rAF 实时同步缩放 & 缩略图 =====
  useEffect(() => {
    let rafId: number;
    let prevZoom = -1;
    let prevVisLeft = Infinity;
    let prevVisTop = Infinity;
    const loop = () => {
      const graph = graphRef.current;
      if (graph && graph.getCanvasByViewport) {
        try {
          const el = containerRef.current;
          const vw = el?.clientWidth || 800;
          const vh = el?.clientHeight || 600;
          const tl = graph.getCanvasByViewport([0, 0]);
          const br = graph.getCanvasByViewport([vw, vh]);
          if (tl && br) {
            const tlX = Array.isArray(tl) ? tl[0] : (tl as any).x;
            const tlY = Array.isArray(tl) ? tl[1] : (tl as any).y;
            const brX = Array.isArray(br) ? br[0] : (br as any).x;
            const brY = Array.isArray(br) ? br[1] : (br as any).y;
            const visW = brX - tlX;
            const z = visW > 0 ? vw / visW : (graph.getZoom?.() ?? 1);
            if (Math.abs(z - prevZoom) > 0.001 || Math.abs(tlX - prevVisLeft) > 0.5 || Math.abs(tlY - prevVisTop) > 0.5) {
              prevZoom = z; prevVisLeft = tlX; prevVisTop = tlY;
              setZoomLevelStable(z);
              viewportRef.current = {
                x: tlX + visW / 2, y: tlY + (brY - tlY) / 2,
                width: vw, height: vh, zoom: z,
              };
              if (minimapOpenRef.current && !minimapDragging.current) drawMinimapRef.current?.();
            }
          }
        } catch (_) {}
      } else if (graph) {
        try {
          const z = graph.getZoom?.() ?? 1;
          if (Math.abs(z - prevZoom) > 0.001) {
            prevZoom = z;
            setZoomLevelStable(z);
          }
        } catch (_) {}
      }
      rafId = requestAnimationFrame(loop);
    };
    rafId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafId);
  }, [setZoomLevelStable]);

  // ===== Resize graph when canvasHeight changes =====
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !containerRef.current) return;
    try {
      graph.resize?.(containerRef.current.clientWidth, canvasHeight);
    } catch (_) {}
  }, [canvasHeight]);

  if (nodes.length === 0) {
    return (
      <Card style={{ borderRadius: 8 }}>
        <div style={{ height: canvasHeight, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="暂无语义网络数据，请先通过数据摄入添加实体" />
        </div>
      </Card>
    );
  }

  return (
    <div ref={wrapperRef}>
    <Card style={{ borderRadius: 8 }} styles={{ body: { padding: 0 } }}>
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <GraphToolbar
          onRefresh={onRefresh}
          layout={layout}
          onLayoutChange={setLayout}
          searchText={searchText}
          onSearchChange={setSearchText}
          filterType={filterType}
          onFilterChange={setFilterType}
          entityTypes={entityTypes}
          versions={versions}
          currentVersion={currentVersion}
          onVersionChange={onVersionChange}
          versionsLoading={versionsLoading}
          showAudit={showAudit}
          onShowAuditChange={setShowAudit}
        />
      </div>
      <div style={{ position: 'relative' }}>
        <div
          ref={containerRef}
          style={{
            width: '100%',
            height: canvasHeight,
            background: '#f5f7fa',
            borderRadius: 4,
            cursor: 'grab',
          }}
        />

        <div
          style={{
            position: 'absolute',
            bottom: 20,
            right: 20,
            display: 'flex',
            alignItems: 'flex-end',
            gap: 0,
            zIndex: 10,
          }}
        >
          {minimapOpen && (
            <div
              style={{
                background: 'rgba(255,255,255,0.85)',
                backdropFilter: 'blur(4px)',
                borderRadius: '8px 0 0 8px',
                padding: 4,
                boxShadow: '0 2px 12px rgba(0,0,0,0.12)',
                userSelect: 'none',
              }}
            >
              <canvas
                ref={minimapCanvasRef}
                width={MINIMAP_WIDTH * devicePixelRatio}
                height={MINIMAP_HEIGHT * devicePixelRatio}
                style={{
                  width: MINIMAP_WIDTH,
                  height: MINIMAP_HEIGHT,
                  cursor: 'pointer',
                  display: 'block',
                  borderRadius: 4,
                  opacity: 0.9,
                }}
                onMouseDown={handleMinimapMouseDown}
                onMouseMove={handleMinimapMouseMove}
                onMouseUp={handleMinimapMouseUp}
              />
              <div style={{ textAlign: 'center', fontSize: 10, color: '#8c8c8c', padding: '2px 0 0' }}>
                拖拽导航
              </div>
            </div>
          )}

          <GraphControls
            zoomLevel={zoomLevel}
            minimapOpen={minimapOpen}
            onCenterView={handleCenterView}
            onZoomIn={handleZoomIn}
            onZoomOut={handleZoomOut}
            onZoomReset={handleZoomReset}
            onToggleMinimap={() => {
              const next = !minimapOpen;
              setMinimapOpen(next);
              if (next) {
                setTimeout(() => {
                  const g = graphRef.current;
                  if (g) {
                    trackViewport(g);
                    updateGraphBounds(g);
                    drawMinimap();
                  }
                }, 50);
              }
            }}
          />
        </div>
      </div>

      <div style={{ marginTop: 0, padding: '8px 16px', fontSize: 12, color: '#8c8c8c', borderTop: '1px solid #f0f0f0' }}>
        <Space size={16}>
          <span>滚轮缩放 · 拖动画布 · 拖动节点 · 点击节点聚焦关联</span>
          <span>缩放: {Math.round(ZOOM_MIN * 100)}%–{Math.round(ZOOM_MAX * 100)}%</span>
          <span>节点: {filteredNodes.length} · 关系: {filteredEdges.length}</span>
          {filterType !== 'all' && (
            <Tag color="blue">已筛选: {filterType} ({filteredNodes.length}个)</Tag>
          )}
        </Space>
      </div>
    </Card>
    </div>
  );
}