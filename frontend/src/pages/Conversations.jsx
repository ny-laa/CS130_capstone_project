import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMessages } from '../api';
import { getUser } from '../auth';
import MessageBubble from '../components/MessageBubble';

// [GenAI Use] Prompt: "Conversations.jsx used to render mock task-grouped
// history plus a 'From Chat' section pulled from TaskContext. Replace
// with a flat list of real messages from GET /api/users/{id}/messages,
// rendered with MessageBubble (already keyed off direction + channel +
// content + timestamp). Backend returns newest first; reverse them so
// the conversation reads top-down chronologically. Group into per-day
// sections with date headers."
// [GenAI Use] LLM Response Start

function formatDayHeader(iso) {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return 'Today';
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
}

function groupByDay(messages) {
  // assumes chronological input (oldest first)
  const groups = [];
  let current = null;
  for (const m of messages) {
    const day = new Date(m.timestamp).toDateString();
    if (!current || current.day !== day) {
      current = { day, label: formatDayHeader(m.timestamp), messages: [] };
      groups.push(current);
    }
    current.messages.push(m);
  }
  return groups;
}

export default function Conversations() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const user = getUser();
    if (!user?.id) {
      navigate('/signin?next=/conversations', { replace: true });
      return;
    }
    let cancelled = false;
    getMessages(user.id, 200)
      .then((rows) => {
        if (cancelled) return;
        // backend returns DESC for fast pagination; humans read top-down
        setMessages([...rows].reverse());
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Failed to load history');
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [navigate]);

  const groups = groupByDay(messages);

  return (
    <div className="page">
      <h1 className="page-title">Conversation History</h1>
      {loading && <p className="task-empty">Loading…</p>}
      {!loading && error && <p className="error-msg">{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <p className="task-empty">No messages yet. Start a chat or text G.</p>
      )}
      {groups.map((g) => (
        <section key={g.day} className="history-day">
          <h2 className="section-title">{g.label}</h2>
          <div className="chat-log">
            {g.messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: dropped the per-task expandable wrapper that
// the mock had -- linking messages back to their parent task can come
// later via the task_id field on each row (already populated for
// scheduled-outbound rows). The flat per-day grouping is the floor;
// we can layer task grouping on top once the audit log has enough rows
// to know how dense it gets. The reverse() is intentional: the API
// returns DESC for fast pagination, but humans read conversations
// top-down chronologically.
