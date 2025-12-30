// Main flow canvas component using ReactFlow

import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { SpanNode } from '../graph/nodes/SpanNode';
import { applyDagreLayout } from '../graph/layout';
import type { FlowGraph, NodeData } from '../types';

// Define custom node types
const nodeTypes = {
  span: SpanNode,
};

interface FlowCanvasProps {
  data: FlowGraph | null;
  highlightedNodes: string[];
  highlightedEdges: string[];
  onNodeClick?: (nodeId: string, data: NodeData) => void;
}

export function FlowCanvas({
  data,
  highlightedNodes,
  highlightedEdges,
  onNodeClick,
}: FlowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Update nodes and edges when data changes
  useEffect(() => {
    if (!data) {
      setNodes([]);
      setEdges([]);
      return;
    }

    // Apply dagre layout
    const layouted = applyDagreLayout(data.nodes, data.edges);

    // Convert to ReactFlow format
    const rfNodes: Node<NodeData>[] = layouted.nodes.map((node) => ({
      id: node.id,
      type: node.type || 'span',
      position: node.position,
      data: node.data,
    }));

    const rfEdges: Edge[] = layouted.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      animated: edge.animated,
      style: {
        stroke: '#30363d',
        strokeWidth: 2,
      },
    }));

    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [data, setNodes, setEdges]);

  // Apply highlighting
  const styledNodes = useMemo(() => {
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        highlighted: highlightedNodes.includes(node.id),
      },
    }));
  }, [nodes, highlightedNodes]);

  const styledEdges = useMemo(() => {
    return edges.map((edge) => ({
      ...edge,
      style: {
        ...edge.style,
        stroke: highlightedEdges.includes(edge.id) ? '#d29922' : '#30363d',
        strokeWidth: highlightedEdges.includes(edge.id) ? 3 : 2,
      },
      animated: highlightedEdges.includes(edge.id) || edge.animated,
    }));
  }, [edges, highlightedEdges]);

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node<NodeData>) => {
      onNodeClick?.(node.id, node.data);
    },
    [onNodeClick]
  );

  if (!data) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📊</div>
        <div>Select a trace to visualize</div>
        <div style={{ fontSize: '13px', marginTop: '8px', color: 'var(--text-secondary)' }}>
          Or record a new trace using the demo endpoints
        </div>
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={styledNodes}
      edges={styledEdges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange as OnNodesChange<Node<NodeData>>}
      onEdgesChange={onEdgesChange as OnEdgesChange<Edge>}
      onNodeClick={handleNodeClick}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      minZoom={0.1}
      maxZoom={2}
    >
      <Background color="#21262d" gap={16} />
      <Controls />
      <MiniMap
        nodeColor={(node) => {
          if ((node.data as NodeData).status === 'error') return '#f85149';
          if ((node.data as NodeData).highlighted) return '#d29922';
          return '#30363d';
        }}
        maskColor="rgba(13, 17, 23, 0.8)"
      />
    </ReactFlow>
  );
}
