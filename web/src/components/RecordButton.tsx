// Record button with dropdown for demo endpoints

import { useState } from 'react';
import * as api from '../api';

interface RecordButtonProps {
  onRecordComplete: (traceId: string) => void;
}

const DEMO_ENDPOINTS = [
  { path: '/demo/fast', label: 'Fast (instant)' },
  { path: '/demo/slow', label: 'Slow (300-800ms)' },
  { path: '/demo/external', label: 'External API call' },
  { path: '/demo/db', label: 'Database query' },
  { path: '/demo/chain', label: 'Nested operations' },
  { path: '/demo/parallel', label: 'Parallel workers' },
  { path: '/demo/mixed', label: 'Mixed workflow' },
  { path: '/demo/error', label: 'Error (500)' },
];

export function RecordButton({ onRecordComplete }: RecordButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRecord = async (path: string) => {
    setLoading(true);
    setError(null);
    setIsOpen(false);

    try {
      const result = await api.recordRequest({
        method: 'GET',
        path,
      });

      if (result.error) {
        setError(result.error);
      } else if (result.traceId) {
        onRecordComplete(result.traceId);
      } else {
        setError('No trace ID returned. The trace may take a moment to appear.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to record');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dropdown">
      <button
        className="btn btn-primary"
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading}
      >
        {loading ? (
          <>
            <span className="spinner" style={{ width: '14px', height: '14px', marginRight: '6px' }} />
            Recording...
          </>
        ) : (
          '⏺ Record Trace'
        )}
      </button>

      {isOpen && (
        <div className="dropdown-menu">
          {DEMO_ENDPOINTS.map((endpoint) => (
            <button
              key={endpoint.path}
              className="dropdown-item"
              onClick={() => handleRecord(endpoint.path)}
            >
              {endpoint.label}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '8px',
            padding: '8px 12px',
            background: 'rgba(248, 81, 73, 0.1)',
            border: '1px solid var(--accent-red)',
            borderRadius: '6px',
            fontSize: '12px',
            color: 'var(--accent-red)',
            maxWidth: '250px',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
