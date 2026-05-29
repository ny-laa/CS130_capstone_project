import { useState, useEffect } from 'react';
import { getTaskHistory } from '../api';
import MessageBubble from '../components/MessageBubble';
import VoiceTranscript from '../components/VoiceTranscript';

// [GenAI Use] LLM Response Start
// Fetches conversations on mount, renders MessageBubble list
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: useEffect empty dep array confirmed correct
// for one-time fetch on mount:
// https://react.dev/reference/react/useEffect#fetching-data-with-effects
// Identified missing loading/error state, needs improvement.

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

export default function TaskHistory() {
  const [tasks, setTasks] = useState([]);

  useEffect(() => {
    getTaskHistory().then(setTasks);
  }, []);

  return (
    <div className="page">
      <h1 className="page-title">Task History</h1>
      <div className="history-list">
        {tasks.map((t) => (
          <TaskHistoryItem key={t.id} task={t} />
        ))}
      </div>
    </div>
  );
}
