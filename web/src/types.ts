// TypeScript types for OpenTrace

// === Graph Types ===

export interface NodeData {
  spanId: string;
  operationName: string;
  serviceName: string;
  duration: number; // milliseconds
  startTime: number;
  status: 'success' | 'error';
  tags: Record<string, unknown>;
  highlighted?: boolean;
}

export interface FlowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: NodeData;
}

export interface EdgeData {
  type: string;
  latencyMs?: number;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  data?: EdgeData;
  animated?: boolean;
}

export interface FlowMeta {
  traceId?: string;
  totalDurationMs?: number;
  spanCount: number;
  serviceCount: number;
  version?: string;
}

export interface FlowGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
  meta: FlowMeta;
}

// === Trace Types ===

export interface TraceSummary {
  traceId: string;
  serviceName: string;
  operationName: string;
  durationMs: number;
  spanCount: number;
  timestamp: number;
  hasError: boolean;
}

// === Agent Types ===

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

export interface Evidence {
  traceId?: string;
  spanIds?: string[];
}

export interface UIHints {
  highlightNodes?: string[];
  highlightEdges?: string[];
  suggestedFilters?: string[];
}

export interface ActionRequest {
  actionType: string;
  description: string;
  params: Record<string, unknown>;
  requiresApproval: boolean;
}

export interface AgentResponse {
  answer: string;
  evidence: Evidence;
  ui: UIHints;
  actions?: ActionRequest[];
}

// === Repo Types ===

export interface RepoInfo {
  repoId: string;
  githubUrl: string;
  status: 'analyzing' | 'ready' | 'building' | 'running' | 'stopped' | 'error';
  language?: 'python' | 'nodejs' | 'unknown';
  framework?: string;
  entrypoint?: string;
  port: number;
  endpoints: string[];
  containerId?: string;
  errorMessage?: string;
}

// === API Types ===

export interface RecordRequest {
  method: string;
  path: string;
  body?: Record<string, unknown>;
  repoId?: string;
}

export interface RecordResponse {
  status: number;
  traceId?: string;
  responseBody?: unknown;
  error?: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  jaegerConnected: boolean;
}
