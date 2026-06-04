import { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { sendChatMessage } from '../api';
import { getUser } from '../auth';
import TypingIndicator from '../components/TypingIndicator';
import SuggestionPills from '../components/SuggestionPills';

// [GenAI Use] Prompt: "Chat.jsx used to talk directly to the Anthropic
// API from the browser, parse <task> XML out of the response, and stash
// the parsed task in a localStorage-backed TaskContext. Replace with a
// single POST to /api/users/{id}/chat -- backend runs the same
// conversation pipeline as real SMS (logs inbound + outbound rows with
// channel='sms', runs Claude, dispatches plan_steps, returns
// {reply, tasks_created}). Drop XML parsing, drop TaskContext, drop
// the sidebar. Messages live in component state only -- leaving the
// page wipes the screen, but the conversation is persisted in the DB
// and surfaces on the History page; any task created via dispatch
// shows up on the Tasks page."
// [GenAI Use] LLM Response Start

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function ChatMessage({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`chat-msg-row${isUser ? ' chat-msg-row--user' : ''}`}>
      {!isUser && <div className="chat-avatar">G</div>}
      <div className="chat-msg-body">
        <div className={`chat-bubble${isUser ? ' chat-bubble--user' : ' chat-bubble--g'}`}>
          <span>{msg.content}</span>
        </div>
        <div className="chat-msg-time">{formatTime(msg.timestamp)}</div>
      </div>
    </div>
  );
}

export default function Chat() {
  const navigate = useNavigate();
  const [userId, setUserId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  // count of tasks created this session, used to show a small banner
  // pointing the user at /tasks. doesn't track ids -- they're persisted
  // on the backend and the Tasks page is the source of truth.
  const [tasksCreatedCount, setTasksCreatedCount] = useState(0);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    const u = getUser();
    if (!u?.id) {
      navigate('/signin?next=/chat', { replace: true });
      return;
    }
    setUserId(u.id);
  }, [navigate]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  const send = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || typing || !userId) return;

    const userMsg = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setTyping(true);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    try {
      const { reply, tasks_created } = await sendChatMessage(userId, trimmed);

      const assistantMsg = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: reply,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (Array.isArray(tasks_created) && tasks_created.length > 0) {
        setTasksCreatedCount((c) => c + tasks_created.length);
      }
    } catch (err) {
      const errMsg = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: err.message?.startsWith('HTTP')
          ? "Sorry, I had trouble reaching the server. Try again?"
          : err.message || "Sorry, something went wrong. Try again?",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setTyping(false);
    }
  }, [typing, userId]);

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  return (
    <div className="chat-page">
      <div className="chat-panel">
        <div className="chat-header">
          <div className="chat-header-avatar">G</div>
          <div className="chat-header-info">
            <h2>G</h2>
            <p>Your AI secretary</p>
          </div>
        </div>

        {tasksCreatedCount > 0 && (
          <div className="chat-banner">
            <span className="chat-banner-icon" aria-hidden="true">✓</span>
            <span className="chat-banner-text">
              {tasksCreatedCount} task{tasksCreatedCount === 1 ? '' : 's'} added this session
            </span>
            <Link to="/tasks" className="chat-banner-link">
              View dashboard →
            </Link>
          </div>
        )}

        <div className="chat-messages">
          {messages.length === 0 ? (
            <SuggestionPills onSelect={send} />
          ) : (
            <>
              {messages.map((msg) => (
                <ChatMessage key={msg.id} msg={msg} />
              ))}
              {typing && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        <div className="chat-input-bar">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder="Message G…"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={typing}
          />
          <button
            className="chat-send-btn"
            onClick={() => send(input)}
            disabled={!input.trim() || typing}
            aria-label="Send"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: dropped the TaskSidebar entirely instead of
// fetching tasks_created by ID on each send. The sidebar was a
// nice-to-have UX nicety; with the Tasks page now real-DB-backed,
// a single line "N tasks added" banner pointing at /tasks gives the
// user the same information at much lower implementation cost. If we
// want richer per-task previews in the sidebar later, fetch
// getTasks(userId) once and filter by tasks_created IDs -- the data
// is all there.
