import Graph from 'graphology';
import { bidirectional as unweightedBidirectional } from 'graphology-shortest-path/unweighted';
import { bidirectional as dijkstraBidirectional } from 'graphology-shortest-path/dijkstra';
import louvain from 'graphology-communities-louvain';
import { degree, betweenness, closeness } from 'graphology-metrics/centrality';
import { connectedComponents } from 'graphology-components';
import type { GraphNode, GraphEdge } from '../types';

export interface ShortestPathResult {
  nodes: string[];
  edges: string[];
  distance: number;
  pathFound: boolean;
}

export interface CommunityResult {
  communities: { [node: string]: number };
  communityColors: Map<number, string>;
  communityCount: number;
}

export interface CentralityResult {
  degree: { [node: string]: number };
  betweenness: { [node: string]: number };
  closeness: { [node: string]: number };
}

export interface ComponentResult {
  components: string[][];
  isolatedCount: number;
}

const COMMUNITY_COLORS = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
  '#F8B500', '#00CED1', '#FF69B4', '#32CD32', '#FF7F50',
];

export function findShortestPath(
  graph: Graph,
  source: string,
  target: string,
  weighted: boolean = false
): ShortestPathResult {
  if (!graph.hasNode(source) || !graph.hasNode(target)) {
    return { nodes: [], edges: [], distance: 0, pathFound: false };
  }

  let nodePath: string[] | null;
  try {
    if (weighted) {
      nodePath = dijkstraBidirectional(graph, source, target);
    } else {
      nodePath = unweightedBidirectional(graph, source, target);
    }
  } catch {
    return { nodes: [], edges: [], distance: 0, pathFound: false };
  }

  if (!nodePath || nodePath.length === 0) {
    return { nodes: [], edges: [], distance: 0, pathFound: false };
  }

  const edges: string[] = [];
  for (let i = 0; i < nodePath.length - 1; i++) {
    const edge = graph.edge(nodePath[i], nodePath[i + 1]);
    if (edge) edges.push(edge);
  }

  return {
    nodes: nodePath,
    edges,
    distance: nodePath.length - 1,
    pathFound: true,
  };
}

export function detectCommunities(graph: Graph): CommunityResult {
  const communities = louvain(graph);
  const communityColors = new Map<number, string>();
  const communityIds = new Set(Object.values(communities));
  const sortedIds = Array.from(communityIds).sort((a, b) => a - b);

  sortedIds.forEach((id, index) => {
    communityColors.set(id, COMMUNITY_COLORS[index % COMMUNITY_COLORS.length]);
  });

  return {
    communities,
    communityColors,
    communityCount: sortedIds.length,
  };
}

export function calculateCentrality(graph: Graph): CentralityResult {
  return {
    degree: degree(graph),
    betweenness: betweenness(graph),
    closeness: closeness(graph),
  };
}

export function findComponents(graph: Graph): ComponentResult {
  const components = connectedComponents(graph);
  const isolatedCount = components.filter((c) => c.length === 1).length;

  return {
    components,
    isolatedCount,
  };
}

export function buildGraphFromData(nodes: GraphNode[], edges: GraphEdge[]): Graph {
  const graph = new Graph({ multi: false, type: 'directed' });

  const validNodes = nodes.filter(n => n.id != null && typeof n.id === 'string' && n.id.trim() !== '');

  for (const n of validNodes) {
    graph.addNode(n.id, {
      label: n.label,
      nodeType: n.type,
      ...n.properties,
    });
  }

  for (const e of edges) {
    if (e.source != null && e.target != null && graph.hasNode(e.source) && graph.hasNode(e.target)) {
      graph.addEdge(e.source, e.target, {
        edgeType: e.type,
        label: e.label || e.type,
      });
    }
  }

  return graph;
}

export function getCommunityColor(communityId: number): string {
  return COMMUNITY_COLORS[communityId % COMMUNITY_COLORS.length];
}
