// Chat panel component for agent interaction

import { useState, useRef, useEffect } from 'react';
import * as api from '../api';
import type { ChatMessage, ActionRequest, AgentResponse } from '../types';

interface ChatPanelProps {
  traceId: string | null;
  onHighlight: (nodeIds: string[], edgeIds: string[]) => void;
  onActionComplete?: (traceId: string) => void;
}

export function ChatPanel({ traceId, onHighlight, onActionComplete }: ChatPanelProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState<ActionRequest | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response: AgentResponse = await api.chat({
        message: userMessage.content,
        selectedTraceId: traceId || undefined,
      });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.answer,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Apply highlighting
      if (response.ui?.highlightNodes?.length || response.ui?.highlightEdges?.length) {
        onHighlight(
          response.ui.highlightNodes || [],
          response.ui.highlightEdges || []
        );
      }

      // Handle action requests
      if (response.actions && response.actions.length > 0) {
        setPendingAction(response.actions[0]);
      }
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAction = async () => {
    if (!pendingAction) return;

    setLoading(true);
    try {
      const result = await api.executeAction({
        actionType: pendingAction.actionType,
        params: pendingAction.params,
      });

      const resultMessage: ChatMessage = {
        role: 'assistant',
        content: result.traceId
          ? `Action completed! Trace ID: ${result.traceId}`
          : `Action completed with status: ${result.status}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, resultMessage]);

      if (result.traceId) {
        onActionComplete?.(result.traceId);
      }
    } catch (err) {
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Action failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setPendingAction(null);
      setLoading(false);
    }
  };

  const handleRejectAction = () => {
    setPendingAction(null);
    const rejectMessage: ChatMessage = {
      role: 'assistant',
      content: 'Action cancelled.',
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, rejectMessage]);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!isOpen) {
    return (
      <button
        className="btn btn-primary"
        style={{
          position: 'fixed',
          bottom: '16px',
          right: '16px',
          zIndex: 1000,
        }}
        onClick={() => setIsOpen(true)}
      >
        💬 Open Chat
      </button>
    );
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span style={{ fontWeight: 500 }}>
          🤖 Trace Assistant
          {traceId && (
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', marginLeft: '8px' }}>
              (analyzing trace)
            </span>
          )}
        </span>
        <button
          className="btn btn-sm"
          onClick={() => setIsOpen(false)}
          style={{ padding: '2px 8px' }}
        >
          ×
        </button>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div style={{ color: 'var(--text-secondary)', fontSize: '13px', textAlign: 'center', padding: '20px' }}>
            Ask me about traces! Try:
            <br />• "What's slow?"
            <br />• "Any errors?"
            <br />• "Explain this trace"
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant" style={{ opacity: 0.7 }}>
            <div className="spinner" style={{ width: '16px', height: '16px', display: 'inline-block', marginRight: '8px' }} />
            Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {pendingAction && (
        <div className="action-approval">
          <div className="action-approval-title">⚠️ Action Requires Approval</div>
          <div style={{ fontSize: '13px' }}>{pendingAction.description}</div>
          <div className="action-approval-buttons">
            <button className="btn btn-success btn-sm" onClick={handleApproveAction}>
              Approve
            </button>
            <button className="btn btn-sm" onClick={handleRejectAction}>
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="chat-input-area">
        <input
          type="text"
          className="chat-input"
          placeholder="Ask about this trace..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={loading}
        />
        <button
          className="btn btn-primary"
          onClick={sendMessage}
          disabled={loading || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
