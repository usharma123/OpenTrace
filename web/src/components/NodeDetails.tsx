// Node details panel component

import type { NodeData } from '../types';

interface NodeDetailsProps {
  node: NodeData | null;
}

export function NodeDetails({ node }: NodeDetailsProps) {
  if (!node) {
    return (
      <div className="node-details">
        <div className="empty-state">
          <div style={{ fontSize: '14px' }}>Click a span to see details</div>
        </div>
      </div>
    );
  }

  const formatDuration = (ms: number) => {
    if (ms < 1) return `${(ms * 1000).toFixed(0)}µs`;
    if (ms < 1000) return `${ms.toFixed(2)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTimestamp = (timestamp: number) => {
    // Timestamp is in microseconds
    const date = new Date(timestamp / 1000);
    return date.toLocaleString();
  };

  // Filter out internal tags
  const displayTags = Object.entries(node.tags || {}).filter(([key]) => {
    return !key.startsWith('otel.') && !key.startsWith('telemetry.');
  });

  return (
    <div className="node-details">
      <div className="node-details-header">
        <span className={`status-badge ${node.status}`}>
          {node.status}
        </span>
        <span style={{ marginLeft: '8px' }}>{node.serviceName}</span>
      </div>

      <div className="node-detail-row">
        <span className="node-detail-label">Operation</span>
        <span className="node-detail-value" title={node.operationName}>
          {node.operationName}
        </span>
      </div>

      <div className="node-detail-row">
        <span className="node-detail-label">Span ID</span>
        <span className="node-detail-value" style={{ fontFamily: 'monospace', fontSize: '11px' }}>
          {node.spanId}
        </span>
      </div>

      <div className="node-detail-row">
        <span className="node-detail-label">Duration</span>
        <span className="node-detail-value" style={{ color: 'var(--accent-yellow)' }}>
          {formatDuration(node.duration)}
        </span>
      </div>

      <div className="node-detail-row">
        <span className="node-detail-label">Start Time</span>
        <span className="node-detail-value" style={{ fontSize: '11px' }}>
          {formatTimestamp(node.startTime)}
        </span>
      </div>

      {displayTags.length > 0 && (
        <div className="node-tags">
          <div className="node-tags-title">Tags</div>
          {displayTags.map(([key, value]) => (
            <div key={key} className="tag-item">
              <span className="tag-key">{key}</span>
              <span className="tag-value" title={String(value)}>
                {String(value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
