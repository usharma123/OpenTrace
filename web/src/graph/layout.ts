// Dagre layout for trace graphs

import dagre from 'dagre';
import type { FlowNode, FlowEdge } from '../types';

const NODE_WIDTH = 220;
const NODE_HEIGHT = 80;

export interface LayoutOptions {
  direction?: 'TB' | 'LR' | 'BT' | 'RL';
  nodeSpacing?: number;
  rankSpacing?: number;
}

export function applyDagreLayout(
  nodes: FlowNode[],
  edges: FlowEdge[],
  options: LayoutOptions = {}
): { nodes: FlowNode[]; edges: FlowEdge[] } {
  const {
    direction = 'TB',
    nodeSpacing = 50,
    rankSpacing = 80,
  } = options;

  // Create dagre graph
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: nodeSpacing,
    ranksep: rankSpacing,
    marginx: 20,
    marginy: 20,
  });

  // Add nodes to dagre
  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    });
  });

  // Add edges to dagre
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  // Calculate layout
  dagre.layout(dagreGraph);

  // Apply positions to nodes
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        // Dagre uses center position, ReactFlow uses top-left
        x: nodeWithPosition.x - NODE_WIDTH / 2,
        y: nodeWithPosition.y - NODE_HEIGHT / 2,
      },
    };
  });

  return {
    nodes: layoutedNodes,
    edges,
  };
}

export function getLayoutedElements(
  nodes: FlowNode[],
  edges: FlowEdge[],
  direction: 'TB' | 'LR' = 'TB'
): { nodes: FlowNode[]; edges: FlowEdge[] } {
  return applyDagreLayout(nodes, edges, { direction });
}
