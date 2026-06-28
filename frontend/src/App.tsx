import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, Bot, User, Loader2 } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          conversation_id: conversationId,
        }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Request failed');
      }

      const data = await response.json();
      setConversationId(data.conversation_id);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.message,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'The request could not be completed. Check that the API server is running and configured.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      maxWidth: '900px',
      margin: '0 auto',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      backgroundColor: '#f8fafc',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px',
        backgroundColor: '#1e293b',
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
      }}>
        <Bot size={28} />
        <div>
          <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 600 }}>ResearchAgent</h1>
          <p style={{ margin: 0, fontSize: '13px', opacity: 0.7 }}>AI Research Assistant</p>
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}>
        {messages.length === 0 && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#64748b',
            textAlign: 'center',
          }}>
            <Bot size={64} strokeWidth={1} />
            <h2 style={{ marginTop: '16px', fontWeight: 500 }}>How can I help you research?</h2>
            <p style={{ maxWidth: '400px', lineHeight: 1.6 }}>
              Ask me to search for information, analyze data, read documents, or generate research reports.
            </p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '24px', flexWrap: 'wrap', justifyContent: 'center' }}>
              {['Search for AI trends', 'Analyze my CSV data', 'Generate a research report'].map(suggestion => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  style={{
                    padding: '8px 16px',
                    border: '1px solid #e2e8f0',
                    borderRadius: '20px',
                    background: 'white',
                    cursor: 'pointer',
                    fontSize: '14px',
                    color: '#475569',
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} style={{
            display: 'flex',
            gap: '12px',
            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            {msg.role === 'assistant' && (
              <div style={{
                width: '36px', height: '36px', borderRadius: '50%',
                backgroundColor: '#3b82f6', display: 'flex',
                alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <Bot size={20} color="white" />
              </div>
            )}
            <div style={{
              maxWidth: '70%',
              padding: '12px 16px',
              borderRadius: '16px',
              backgroundColor: msg.role === 'user' ? '#3b82f6' : 'white',
              color: msg.role === 'user' ? 'white' : '#1e293b',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
              lineHeight: 1.6,
              fontSize: '14px',
            }}>
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
            {msg.role === 'user' && (
              <div style={{
                width: '36px', height: '36px', borderRadius: '50%',
                backgroundColor: '#10b981', display: 'flex',
                alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <User size={20} color="white" />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '50%',
              backgroundColor: '#3b82f6', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            }}>
              <Bot size={20} color="white" />
            </div>
            <div style={{
              padding: '12px 16px', borderRadius: '16px',
              backgroundColor: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            }}>
              <Loader2 size={20} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: '16px 24px',
        borderTop: '1px solid #e2e8f0',
        backgroundColor: 'white',
      }}>
        <div style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-end',
        }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask a research question..."
            rows={1}
            style={{
              flex: 1,
              padding: '12px 16px',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              resize: 'none',
              fontSize: '14px',
              fontFamily: 'inherit',
              outline: 'none',
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            style={{
              padding: '12px',
              backgroundColor: input.trim() ? '#3b82f6' : '#e2e8f0',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              cursor: input.trim() ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Send size={20} />
          </button>
        </div>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default App;
