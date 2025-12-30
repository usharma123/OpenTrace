// Trace list sidebar component

import { useEffect, useState } from 'react';
import * as api from '../api';
import type { TraceSummary } from '../types';

interface TraceListProps {
  selectedTraceId: string | null;
  onSelectTrace: (traceId: string) => void;
  onRefresh?: () => void;
}

export function TraceList({ selectedTraceId, onSelectTrace, onRefresh }: TraceListProps) {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTraces = async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await api.searchTraces({ limit: 30, lookback: '1h' });
      setTraces(results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch traces');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTraces();
    // Poll for new traces every 10 seconds
    const interval = setInterval(fetchTraces, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    fetchTraces();
    onRefresh?.();
  };

  const formatTime = (timestamp: number) => {
    // Timestamp is in microseconds
    const date = new Date(timestamp / 1000);
    return date.toLocaleTimeString();
  };

  if (loading && traces.length === 0) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading traces...
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div style={{ color: 'var(--accent-red)' }}>{error}</div>
        <button className="btn btn-sm" onClick={handleRefresh} style={{ marginTop: '12px' }}>
          Retry
        </button>
      </div>
    );
  }

  if (traces.length === 0) {
    return (
      <div className="empty-state">
        <div>No traces found</div>
        <div style={{ fontSize: '12px', marginTop: '8px', color: 'var(--text-secondary)' }}>
          Record a trace to get started
        </div>
      </div>
    );
  }

  return (
    <div className="trace-list">
      {traces.map((trace) => (
        <div
          key={trace.traceId}
          className={`trace-item ${selectedTraceId === trace.traceId ? 'selected' : ''} ${trace.hasError ? 'has-error' : ''}`}
          onClick={() => onSelectTrace(trace.traceId)}
        >
          <div className="trace-operation" title={trace.operationName}>
            {trace.operationName}
          </div>
          <div className="trace-meta">
            <span className="trace-time">{formatTime(trace.timestamp)}</span>
            <span className="trace-duration">{trace.durationMs.toFixed(1)}ms</span>
          </div>
          <div className="trace-meta" style={{ marginTop: '2px' }}>
            <span style={{ fontSize: '11px' }}>{trace.serviceName}</span>
            <span style={{ fontSize: '11px' }}>{trace.spanCount} spans</span>
          </div>
        </div>
      ))}
    </div>
  );
}
