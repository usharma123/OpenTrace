// Record button with dropdown for demo endpoints

import { useState } from 'react';
import * as api from '../api';
import type { RepoInfo } from '../types';

interface RecordButtonProps {
  onRecordComplete: (traceId: string) => void;
  activeRepo?: RepoInfo | null;
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

// Common endpoints to try when repo doesn't have detected endpoints
const COMMON_ENDPOINTS = [
  { path: '/', label: 'Root (/)' },
  { path: '/health', label: 'Health Check' },
  { path: '/api', label: 'API Root' },
  { path: '/api/health', label: 'API Health' },
];

export function RecordButton({ onRecordComplete, activeRepo }: RecordButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customPath, setCustomPath] = useState('');

  const handleRecord = async (path: string, repoId?: string) => {
    setLoading(true);
    setError(null);
    setIsOpen(false);

    try {
      const result = await api.recordRequest({
        method: 'GET',
        path,
        repoId,
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

  const handleCustomRecord = () => {
    if (customPath.trim()) {
      const path = customPath.startsWith('/') ? customPath : `/${customPath}`;
      handleRecord(path, activeRepo?.repoId);
      setCustomPath('');
    }
  };

  // Determine which endpoints to show
  const repoEndpoints = activeRepo?.endpoints?.length 
    ? activeRepo.endpoints.map(path => ({ path, label: path }))
    : COMMON_ENDPOINTS;
  
  const isRepoActive = activeRepo?.status === 'running';

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
        <div className="dropdown-menu" style={{ minWidth: '250px' }}>
          {/* Show repo endpoints if a repo is running */}
          {isRepoActive && (
            <>
              <div className="dropdown-header" style={{ 
                padding: '8px 12px', 
                fontSize: '11px', 
                color: 'var(--text-secondary)',
                borderBottom: '1px solid var(--border-color)'
              }}>
                📦 {activeRepo?.repoId?.split('-').slice(0, 2).join('/')}
              </div>
              
              {/* Custom path input */}
              <div style={{ padding: '8px 12px', display: 'flex', gap: '4px' }}>
                <input
                  type="text"
                  className="input"
                  placeholder="/api/endpoint"
                  value={customPath}
                  onChange={(e) => setCustomPath(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCustomRecord()}
                  style={{ flex: 1, padding: '4px 8px', fontSize: '12px' }}
                />
                <button 
                  className="btn btn-sm"
                  onClick={handleCustomRecord}
                  disabled={!customPath.trim()}
                >
                  Go
                </button>
              </div>

              {repoEndpoints.map((endpoint) => (
                <button
                  key={endpoint.path}
                  className="dropdown-item"
                  onClick={() => handleRecord(endpoint.path, activeRepo?.repoId)}
                >
                  {endpoint.label}
                </button>
              ))}
              
              <div style={{ 
                borderTop: '1px solid var(--border-color)',
                margin: '4px 0'
              }} />
              <div className="dropdown-header" style={{ 
                padding: '8px 12px', 
                fontSize: '11px', 
                color: 'var(--text-secondary)'
              }}>
                🧪 Demo Endpoints
              </div>
            </>
          )}
          
          {/* Always show demo endpoints */}
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
