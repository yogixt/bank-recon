import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { chatWithAI } from '../api/endpoints';

interface Message {
  role: 'user' | 'ai';
  text: string;
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  if (!id) return <p>No session ID</p>;

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);

    try {
      const response = await chatWithAI(id, userMsg);
      setMessages((prev) => [...prev, { role: 'ai', text: response }]);
    } catch {
      setMessages((prev) => [...prev, { role: 'ai', text: 'Error getting response. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <h2>AI Chat</h2>
      <div className="card chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '2rem' }}>
              Ask questions about your reconciliation results...
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`chat-message ${m.role}`}>
              <div className="bubble" style={{ whiteSpace: 'pre-wrap' }}>{m.text}</div>
            </div>
          ))}
          {loading && (
            <div className="chat-message ai">
              <div className="bubble">Thinking...</div>
            </div>
          )}
        </div>
        <div className="chat-input">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="Ask about your reconciliation..."
          />
          <button className="btn btn-primary" onClick={send} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </>
  );
}
