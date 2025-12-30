// Custom node component for spans

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { NodeData } from '../../types';

interface SpanNodeProps extends NodeProps {
  data: NodeData;
}

function SpanNodeComponent({ data }: SpanNodeProps) {
  const isError = data.status === 'error';
  const isHighlighted = data.highlighted;

  const classNames = [
    'span-node',
    isError ? 'error' : '',
    isHighlighted ? 'highlighted' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={classNames}>
      <Handle type="target" position={Position.Top} />

      <div className="span-node-header">
        <span className="span-node-service">{data.serviceName}</span>
        <span className={`span-node-status ${data.status}`}>
          {data.status === 'error' ? 'ERR' : 'OK'}
        </span>
      </div>

      <div className="span-node-operation" title={data.operationName}>
        {data.operationName}
      </div>

      <div className="span-node-metrics">
        <span className="span-node-duration">
          {data.duration.toFixed(1)}ms
        </span>
        {data.tags?.['http.status_code'] && (
          <span className="span-node-http-status">
            HTTP {data.tags['http.status_code'] as number}
          </span>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

export const SpanNode = memo(SpanNodeComponent);
