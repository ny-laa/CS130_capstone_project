import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMessages } from '../api';
import { getUser } from '../auth';
import MessageBubble from '../components/MessageBubble';

// [GenAI Use] Prompt: "Conversations.jsx used to render a flat
// chronological message list grouped by day, which made it hard to
// browse later. Group consecutive messages into sessions (a single
// call, a single SMS thread, a single chat session) using two heuristics:
// (1) channel boundary -- voice <-> sms ends a session; (2) gap > 30
// minutes ends a session. Render each session as its own card with a
// channel badge (Call vs SMS, since browser chat is logged with
// channel='sms' too), a relative header (Today / Yesterday / dated),
// and the messages inside chronologically. Sort sessions newest-first
// by their first message."
// [GenAI Use] LLM Response Start

// 30 minutes of inactivity = next message starts a new session. Tuned
// for human chat cadence -- short enough that the morning thread doesn't
// merge with the evening thread, long enough that thinking-of-a-reply
// pauses don't artificially split a single back-and-forth.
const SESSION_GAP_MS = 30 * 60 * 1000;

function formatSessionHeader(iso) {
  const d = new Date(iso);
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === today) return `Today · ${time}`;
  if (d.toDateString() === yesterday.toDateString()) return `Yesterday · ${time}`;
  return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }) + ` · ${time}`;
}

function channelLabel(channel) {
  if (channel === 'voice') return { icon: '📞', label: 'Call' };
  // SMS bucket includes the browser Chat tab (logged with channel='sms').
  return { icon: '💬', label: 'SMS' };
}

// Walk chronological messages, break into sessions on channel change or
// long gap. Returns sessions in chronological order; caller reverses for
// newest-first display.
function groupIntoSessions(messages) {
  const sessions = [];
  let current = null;
  for (const m of messages) {
    const ts = new Date(m.timestamp).getTime();
    const sameChannel = current && current.channel === m.channel;
    const withinGap = current && ts - current.lastTs <= SESSION_GAP_MS;
    if (current && sameChannel && withinGap) {
      current.messages.push(m);
      current.lastTs = ts;
    } else {
      current = {
        id: m.id, // first message id stands in as a stable session key
        channel: m.channel,
        startedAt: m.timestamp,
        lastTs: ts,
        messages: [m],
      };
      sessions.push(current);
    }
  }
  return sessions;
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
        // backend returns DESC for fast pagination; we want chronological
        // for the grouping algorithm. We'll reverse session order at the
        // render step.
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

  // newest session first; messages within each session stay chronological
  const sessions = groupIntoSessions(messages).reverse();

  return (
    <div className="page">
      <h1 className="page-title">Conversation History</h1>
      {loading && <p className="task-empty">Loading…</p>}
      {!loading && error && <p className="error-msg">{error}</p>}
      {!loading && !error && messages.length === 0 && (
        <p className="task-empty">No messages yet. Start a chat or text G.</p>
      )}
      <div className="history-list">
        {sessions.map((s) => {
          const { icon, label } = channelLabel(s.channel);
          return (
            <section key={s.id} className="history-item history-item--open">
              <div className="history-item-header" style={{ cursor: 'default' }}>
                <div className="history-item-meta">
                  <div className="history-item-details">
                    <span className="badge badge-channel">{icon} {label}</span>
                    <span className="badge badge-status">{s.messages.length} message{s.messages.length === 1 ? '' : 's'}</span>
                  </div>
                  <p className="history-item-timestamps">{formatSessionHeader(s.startedAt)}</p>
                </div>
              </div>
              <div className="history-item-body">
                <div className="chat-log chat-log--compact">
                  {s.messages.map((m) => (
                    <MessageBubble key={m.id} message={m} />
                  ))}
                </div>
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: kept the grouping heuristic in a pure helper
// so it's testable in isolation later. The two-rule cutoff (channel
// boundary + 30-minute gap) handles the demo cases: a single back-and-
// forth call shows as one card, a chat session shows as one card, and
// if the user texts G in the morning and again in the evening they get
// two SMS cards instead of one mega-thread. If/when we add an explicit
// session_id column to messages this collapses into one-line grouping
// by that id -- but inference works fine until then.
