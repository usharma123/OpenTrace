// API client for OpenTrace

import type {
  FlowGraph,
  TraceSummary,
  AgentResponse,
  RecordRequest,
  RecordResponse,
  HealthResponse,
  RepoInfo,
} from './types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const AGENT_URL = import.meta.env.VITE_AGENT_URL || 'http://localhost:8081';

// === Health ===

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) throw new Error('Health check failed');
  return response.json();
}

export async function checkAgentHealth(): Promise<{ llm_available: boolean }> {
  const response = await fetch(`${AGENT_URL}/health`);
  if (!response.ok) throw new Error('Agent health check failed');
  return response.json();
}

// === Flows ===

export async function getRuntimeFlow(traceId: string): Promise<FlowGraph> {
  const response = await fetch(`${API_URL}/flows/runtime/${traceId}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Trace ${traceId} not found`);
    }
    throw new Error('Failed to fetch runtime flow');
  }
  return response.json();
}

export async function getStaticFlow(): Promise<FlowGraph> {
  const response = await fetch(`${API_URL}/flows/static`);
  if (!response.ok) throw new Error('Failed to fetch static flow');
  return response.json();
}

// === Traces ===

export async function searchTraces(params?: {
  service?: string;
  lookback?: string;
  limit?: number;
}): Promise<TraceSummary[]> {
  const searchParams = new URLSearchParams();
  if (params?.service) searchParams.set('service', params.service);
  if (params?.lookback) searchParams.set('lookback', params.lookback);
  if (params?.limit) searchParams.set('limit', String(params.limit));

  const url = `${API_URL}/traces/search?${searchParams}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to search traces');
  return response.json();
}

export async function getTrace(traceId: string): Promise<unknown> {
  const response = await fetch(`${API_URL}/traces/${traceId}`);
  if (!response.ok) throw new Error('Failed to fetch trace');
  return response.json();
}

export async function getTraceAnalysis(traceId: string): Promise<{
  traceId: string;
  criticalPath: string[];
  slowestSpans: Array<{ spanId: string; operationName: string; durationMs: number }>;
  errorSpans: Array<{ spanId: string; operationName: string }>;
}> {
  const response = await fetch(`${API_URL}/traces/${traceId}/analysis`);
  if (!response.ok) throw new Error('Failed to fetch trace analysis');
  return response.json();
}

// === Services ===

export async function getServices(): Promise<{ services: string[] }> {
  const response = await fetch(`${API_URL}/services`);
  if (!response.ok) throw new Error('Failed to fetch services');
  return response.json();
}

// === Record ===

export async function recordRequest(request: RecordRequest): Promise<RecordResponse> {
  const response = await fetch(`${API_URL}/record`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error('Failed to record request');
  return response.json();
}

// === Agent ===

export async function chat(params: {
  message: string;
  selectedTraceId?: string;
}): Promise<AgentResponse> {
  const response = await fetch(`${AGENT_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!response.ok) throw new Error('Failed to chat with agent');
  return response.json();
}

export async function executeAction(action: {
  actionType: string;
  params: Record<string, unknown>;
}): Promise<RecordResponse> {
  const response = await fetch(`${AGENT_URL}/execute-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  });
  if (!response.ok) throw new Error('Failed to execute action');
  return response.json();
}

// === Repos ===

export async function analyzeRepo(githubUrl: string): Promise<RepoInfo> {
  const response = await fetch(`${API_URL}/repos/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ githubUrl }),
  });
  if (!response.ok) throw new Error('Failed to analyze repo');
  return response.json();
}

export async function getRepo(repoId: string): Promise<RepoInfo> {
  const response = await fetch(`${API_URL}/repos/${repoId}`);
  if (!response.ok) throw new Error('Failed to fetch repo');
  return response.json();
}

export async function startRepo(repoId: string): Promise<RepoInfo> {
  const response = await fetch(`${API_URL}/repos/${repoId}/start`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to start repo');
  return response.json();
}

export async function stopRepo(repoId: string): Promise<RepoInfo> {
  const response = await fetch(`${API_URL}/repos/${repoId}/stop`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to stop repo');
  return response.json();
}

export async function listRepos(): Promise<{ repos: RepoInfo[] }> {
  const response = await fetch(`${API_URL}/repos`);
  if (!response.ok) throw new Error('Failed to list repos');
  return response.json();
}
