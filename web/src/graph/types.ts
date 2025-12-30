// Graph-specific types

import type { Node, Edge } from '@xyflow/react';
import type { NodeData } from '../types';

export type SpanNodeType = Node<NodeData, 'span'>;
export type ServiceNodeType = Node<NodeData, 'service'>;

export type GraphNode = SpanNodeType | ServiceNodeType;
export type GraphEdge = Edge;

export interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  highlightedNodeIds: string[];
  highlightedEdgeIds: string[];
}
