// Main App component

import { useState, useEffect, useCallback } from 'react';
import { ReactFlowProvider } from '@xyflow/react';
import { FlowCanvas } from './components/FlowCanvas';
import { TraceList } from './components/TraceList';
import { NodeDetails } from './components/NodeDetails';
import { ChatPanel } from './components/ChatPanel';
import { RecordButton } from './components/RecordButton';
import { RepoInput } from './components/RepoInput';
import * as api from './api';
import type { FlowGraph, NodeData, RepoInfo } from './types';

type ViewMode = 'runtime' | 'static' | 'overlay';

function App() {
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [flowData, setFlowData] = useState<FlowGraph | null>(null);
  const [selectedNode, setSelectedNode] = useState<NodeData | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<string[]>([]);
  const [highlightedEdges, setHighlightedEdges] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('runtime');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeRepo, setActiveRepo] = useState<RepoInfo | null>(null);
  const [jaegerConnected, setJaegerConnected] = useState(false);

  // Check health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await api.checkHealth();
        setJaegerConnected(health.jaegerConnected);
      } catch {
        setJaegerConnected(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch flow data when trace is selected
  useEffect(() => {
    if (!selectedTraceId) {
      if (viewMode !== 'static') {
        setFlowData(null);
      }
      return;
    }

    const fetchFlow = async () => {
      setLoading(true);
      setError(null);
      try {
        if (viewMode === 'static') {
          const data = await api.getStaticFlow();
          setFlowData(data);
        } else {
          const data = await api.getRuntimeFlow(selectedTraceId);
          setFlowData(data);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch flow');
        setFlowData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchFlow();
  }, [selectedTraceId, viewMode]);

  // Fetch static flow when mode changes
  useEffect(() => {
    if (viewMode === 'static') {
      const fetchStatic = async () => {
        setLoading(true);
        try {
          const data = await api.getStaticFlow();
          setFlowData(data);
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Failed to fetch static flow');
        } finally {
          setLoading(false);
        }
      };
      fetchStatic();
    }
  }, [viewMode]);

  const handleSelectTrace = useCallback((traceId: string) => {
    setSelectedTraceId(traceId);
    setSelectedNode(null);
    setHighlightedNodes([]);
    setHighlightedEdges([]);
    if (viewMode === 'static') {
      setViewMode('runtime');
    }
  }, [viewMode]);

  const handleNodeClick = useCallback((_nodeId: string, data: NodeData) => {
    setSelectedNode(data);
  }, []);

  const handleHighlight = useCallback((nodeIds: string[], edgeIds: string[]) => {
    setHighlightedNodes(nodeIds);
    setHighlightedEdges(edgeIds);
  }, []);

  const handleRecordComplete = useCallback((traceId: string) => {
    // Wait a moment for Jaeger to index the trace, then select it
    setTimeout(() => {
      setSelectedTraceId(traceId);
    }, 1000);
  }, []);

  const handleRepoReady = useCallback((repo: RepoInfo) => {
    setActiveRepo(repo);
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <span>📊</span>
            <span>OpenTrace</span>
          </div>

          <div className="toggle-group">
            <button
              className={`toggle-btn ${viewMode === 'runtime' ? 'active' : ''}`}
              onClick={() => setViewMode('runtime')}
            >
              Runtime
            </button>
            <button
              className={`toggle-btn ${viewMode === 'static' ? 'active' : ''}`}
              onClick={() => setViewMode('static')}
            >
              Static
            </button>
          </div>

          <RepoInput onRepoReady={handleRepoReady} />
        </div>

        <div className="header-right">
          {activeRepo && activeRepo.status === 'running' && (
            <span style={{ fontSize: '12px', color: 'var(--accent-green)' }}>
              🟢 {activeRepo.repoId} running on port {activeRepo.port}
            </span>
          )}

          <span
            style={{
              fontSize: '12px',
              color: jaegerConnected ? 'var(--accent-green)' : 'var(--accent-red)',
            }}
          >
            {jaegerConnected ? '● Jaeger connected' : '○ Jaeger disconnected'}
          </span>

          <RecordButton onRecordComplete={handleRecordComplete} activeRepo={activeRepo} />

          <a
            href="http://localhost:16686"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm"
          >
            Open Jaeger UI
          </a>
        </div>
      </header>

      <main className="main">
        <aside className="sidebar">
          <div className="sidebar-header">
            Recent Traces
          </div>
          <div className="sidebar-content">
            <TraceList
              selectedTraceId={selectedTraceId}
              onSelectTrace={handleSelectTrace}
            />
          </div>
        </aside>

        <div className="canvas-area">
          {loading ? (
            <div className="loading">
              <div className="spinner" />
              Loading flow...
            </div>
          ) : error ? (
            <div className="empty-state">
              <div style={{ color: 'var(--accent-red)' }}>{error}</div>
            </div>
          ) : (
            <ReactFlowProvider>
              <FlowCanvas
                data={flowData}
                highlightedNodes={highlightedNodes}
                highlightedEdges={highlightedEdges}
                onNodeClick={handleNodeClick}
              />
            </ReactFlowProvider>
          )}
        </div>

        <aside className="details-panel">
          <div className="sidebar-header">
            Span Details
          </div>
          <NodeDetails node={selectedNode} />
        </aside>
      </main>

      <ChatPanel
        traceId={selectedTraceId}
        onHighlight={handleHighlight}
        onActionComplete={handleRecordComplete}
      />
    </div>
  );
}

export default App;
