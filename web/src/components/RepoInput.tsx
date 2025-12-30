// GitHub repository input and analysis component

import { useState } from 'react';
import * as api from '../api';
import type { RepoInfo } from '../types';

interface RepoInputProps {
  onRepoReady: (repo: RepoInfo) => void;
}

export function RepoInput({ onRepoReady }: RepoInputProps) {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [repo, setRepo] = useState<RepoInfo | null>(null);

  const handleAnalyze = async () => {
    if (!url.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await api.analyzeRepo(url.trim());
      setRepo(result);

      // Poll for status updates
      if (result.status === 'analyzing') {
        pollStatus(result.repoId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze repo');
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = async (repoId: string) => {
    try {
      const result = await api.getRepo(repoId);
      setRepo(result);

      if (result.status === 'analyzing' || result.status === 'building') {
        setTimeout(() => pollStatus(repoId), 2000);
      } else if (result.status === 'ready' || result.status === 'running') {
        onRepoReady(result);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get status');
    }
  };

  const handleStart = async () => {
    if (!repo) return;

    setLoading(true);
    try {
      const result = await api.startRepo(repo.repoId);
      setRepo(result);

      if (result.status === 'building') {
        pollStatus(result.repoId);
      } else if (result.status === 'running') {
        onRepoReady(result);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start repo');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!repo) return;

    setLoading(true);
    try {
      const result = await api.stopRepo(repo.repoId);
      setRepo(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop repo');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'var(--accent-green)';
      case 'error':
        return 'var(--accent-red)';
      case 'analyzing':
      case 'building':
        return 'var(--accent-yellow)';
      default:
        return 'var(--text-secondary)';
    }
  };

  return (
    <div className="repo-input-container">
      <input
        type="text"
        className="input repo-input"
        placeholder="https://github.com/user/repo"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={loading}
      />
      <button
        className="btn"
        onClick={handleAnalyze}
        disabled={loading || !url.trim()}
      >
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>

      {repo && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              background: 'var(--bg-tertiary)',
              color: getStatusColor(repo.status),
            }}
          >
            {repo.status}
          </span>

          {repo.language && (
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              {repo.language}
            </span>
          )}

          {repo.status === 'ready' && (
            <button className="btn btn-success btn-sm" onClick={handleStart}>
              Start
            </button>
          )}

          {repo.status === 'running' && (
            <button className="btn btn-danger btn-sm" onClick={handleStop}>
              Stop
            </button>
          )}
        </div>
      )}

      {error && (
        <span style={{ fontSize: '12px', color: 'var(--accent-red)' }}>
          {error}
        </span>
      )}
    </div>
  );
}
