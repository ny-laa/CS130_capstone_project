import { useState, useEffect } from 'react';
import { getTaskHistory } from '../api';
import MessageBubble from '../components/MessageBubble';
import VoiceTranscript from '../components/VoiceTranscript';
import { useTasks } from '../context/TaskContext';

// [GenAI Use] LLM Response Start
// Fetches conversations on mount, renders MessageBubble list
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: useEffect empty dep array confirmed correct
// for one-time fetch on mount:
// https://react.dev/reference/react/useEffect#fetching-data-with-effects
// Identified missing loading/error state, needs improvement.

// [GenAI Use] LLM Response Start UPDATE
// Added a "From Chat" section at the top for context tasks that
// reached Completed or Failed status.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Filters TaskContext for tasks with
// Completed or Failed status and shows them at the top as a
// separate section. Good way to see the history of what the AI
// actually did.


const STATUS_COLORS = {
  COMPLETED: '#10b981',
  FAILED: '#6b7280',
};

const STATUS_LABELS = {
  COMPLETED: 'Completed',
  FAILED: 'Failed',
};

function formatDuration(createdAt, completedAt) {
  const ms = new Date(completedAt) - new Date(createdAt);
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `${hrs}h ${rem}m` : `${hrs}h`;
}

function formatDate(ts) {
  return new Date(ts).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function TaskHistoryItem({ task }) {
  const [open, setOpen] = useState(false);
  const { description, type, status, createdAt, completedAt, channel, conversation, transcript, callDuration } = task;

  return (
    <div className={`history-item${open ? ' history-item--open' : ''}`}>
      <button className="history-item-header" onClick={() => setOpen((o) => !o)}>
        <div className="history-item-meta">
          <p className="history-item-description">{description}</p>
          <div className="history-item-details">
            <span className="badge badge-type">{type}</span>
            <span
              className="badge badge-status"
              style={{ background: STATUS_COLORS[status] }}
            >
              {STATUS_LABELS[status]}
            </span>
            <span className="badge badge-channel">
              {channel === 'voice' ? '⊙ Voice' : '◎ SMS'}
            </span>
          </div>
          <p className="history-item-timestamps">
            {formatDate(createdAt)} · Completed in {formatDuration(createdAt, completedAt)}
          </p>
        </div>
        <span className={`history-chevron${open ? ' history-chevron--open' : ''}`}>›</span>
      </button>

      {open && (
        <div className="history-item-body">
          {channel === 'sms' && conversation && (
            <div className="chat-log chat-log--compact">
              {conversation.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
            </div>
          )}
          {channel === 'voice' && transcript && (
            <VoiceTranscript transcript={transcript} duration={callDuration} />
          )}
        </div>
      )}
    </div>
  );
}

const CHAT_STATUS_COLORS = { COMPLETED: '#10b981', FAILED: '#6b7280' };
const CHAT_STATUS_LABELS = { COMPLETED: 'Completed', FAILED: 'Failed' };

function ChatTaskHistoryItem({ task }) {
  const { description, type, status, createdAt, summary } = task;
  return (
    <div className="history-item">
      <div className="history-item-header" style={{ cursor: 'default' }}>
        <div className="history-item-meta">
          <p className="history-item-description">{description}</p>
          <div className="history-item-details">
            <span className="badge badge-type">{type}</span>
            <span className="badge badge-status" style={{ background: CHAT_STATUS_COLORS[status] }}>
              {CHAT_STATUS_LABELS[status]}
            </span>
            <span className="badge badge-channel">💬 Chat</span>
          </div>
          <p className="history-item-timestamps">
            {new Date(createdAt).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            {summary && ` · ${summary}`}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function TaskHistory() {
  const [history, setHistory] = useState([]);
  const { tasks } = useTasks();

  useEffect(() => {
    getTaskHistory().then(setHistory);
  }, []);

  const chatCompleted = tasks.filter(
    (t) => (t.status === 'COMPLETED' || t.status === 'FAILED') && t.id.startsWith('chat-task-')
  );

  return (
    <div className="page">
      <h1 className="page-title">Task History</h1>
      {chatCompleted.length > 0 && (
        <>
          <h2 className="section-title">From Chat</h2>
          <div className="history-list" style={{ marginBottom: 24 }}>
            {chatCompleted.map((t) => (
              <ChatTaskHistoryItem key={t.id} task={t} />
            ))}
          </div>
          <h2 className="section-title">All History</h2>
        </>
      )}
      <div className="history-list">
        {history.map((t) => (
          <TaskHistoryItem key={t.id} task={t} />
        ))}
      </div>
    </div>
  );
}
