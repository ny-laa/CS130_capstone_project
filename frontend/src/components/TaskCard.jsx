import { useState, useEffect } from 'react';
import { approveEscalation, denyEscalation } from '../api';
import { useTasks } from '../context/TaskContext';

// [GenAI Use] LLM Response Start
// STATUS_COLORS/LABELS maps, formatDate, useCountdown hook,
// approve/deny escalation buttons
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Verified countdown math (30 * 60 * 1000ms).
// Consulted setInterval cleanup docs to confirm no memory leak:
// https://developer.mozilla.org/en-US/docs/Web/API/setInterval
// Confirmed api.js mock functions match expected signature.

// [GenAI Use] LLM Response Start UPDATE
// Approve/Deny now calls updateTask() so status change saves to
// context and localStorage.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Before this change, approve/deny only
// updated local state so the change was lost on navigation. Now it
// goes through context so it persists. Verified the badge count in
// NavBar drops when an escalation is approved or denied.

const STATUS_COLORS = {
  PENDING: '#f59e0b',
  IN_PROGRESS: '#3b5bdb',
  ESCALATION_PENDING: '#ef4444',
  COMPLETED: '#10b981',
  FAILED: '#6b7280',
};

const STATUS_LABELS = {
  PENDING: 'Pending',
  IN_PROGRESS: 'In Progress',
  ESCALATION_PENDING: 'Needs Approval',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
};

function formatDate(ts) {
  return new Date(ts).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// 30-minute countdown from escalationCreatedAt
function useCountdown(targetIso) {
  const getRemaining = () => {
    const end = new Date(targetIso).getTime() + 30 * 60 * 1000;
    return Math.max(0, end - Date.now());
  };

  const [remaining, setRemaining] = useState(getRemaining);

  useEffect(() => {
    const id = setInterval(() => setRemaining(getRemaining()), 1000);
    return () => clearInterval(id);
  }, [targetIso]);

  if (remaining === 0) return 'Expired';
  const mins = Math.floor(remaining / 60000);
  const secs = Math.floor((remaining % 60000) / 1000);
  return `${mins}m ${secs.toString().padStart(2, '0')}s`;
}

function EscalationSection({ taskId, question, escalationCreatedAt, onAction }) {
  const countdown = useCountdown(escalationCreatedAt);
  const { updateTask } = useTasks();
  const [loading, setLoading] = useState(false);
  const [popup, setPopup] = useState(null); // 'approved' | 'denied'

  async function handle(action) {
    setLoading(true);
    try {
      if (action === 'approve') {
        await approveEscalation(taskId);
        updateTask(taskId, { status: 'COMPLETED', summary: 'Escalation approved.' });
      } else {
        await denyEscalation(taskId);
        updateTask(taskId, { status: 'FAILED', summary: 'Escalation denied.' });
      }
      setPopup(action === 'approve' ? 'approved' : 'denied');
      setTimeout(() => {
        setPopup(null);
        if (onAction) onAction(action);
      }, 2500);
    } catch {
      // keep buttons enabled so the user can retry
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {popup && (
        <div className="escalation-popup-overlay" onClick={() => { setPopup(null); if (onAction) onAction(popup); }}>
          <div className="escalation-popup">
            <div className="escalation-popup-icon">{popup === 'approved' ? '✅' : '🚫'}</div>
            <p className="escalation-popup-title" style={{ color: popup === 'approved' ? '#10b981' : '#ef4444' }}>
              {popup === 'approved' ? 'Task Approved' : 'Task Denied'}
            </p>
            <p className="escalation-popup-sub">
              {popup === 'approved' ? 'G will proceed with this action.' : 'G will not proceed with this action.'}
            </p>
          </div>
        </div>
      )}
      <div className="escalation-section">
        <p className="escalation-question">{question}</p>
        <div className="escalation-footer">
          <span className="escalation-timer">Expires in {countdown}</span>
          <div className="escalation-actions">
            <button className="btn-approve" onClick={() => handle('approve')} disabled={loading}>
              {loading ? '…' : 'Approve'}
            </button>
            <button className="btn-deny" onClick={() => handle('deny')} disabled={loading}>
              {loading ? '…' : 'Deny'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default function TaskCard({ task, onEscalationAction }) {
  const { id, description, type, status, createdAt, summary, escalationQuestion, escalationCreatedAt } = task;

  return (
    <div className="task-card">
      <div className="task-card-header">
        <p className="task-description">{description}</p>
        <div className="task-badges">
          <span className="badge badge-type">{type}</span>
          <span className="badge badge-status" style={{ background: STATUS_COLORS[status] }}>
            {STATUS_LABELS[status]}
          </span>
        </div>
      </div>
      <p className="task-created">Created {formatDate(createdAt)}</p>

      {status === 'ESCALATION_PENDING' && escalationQuestion && (
        <EscalationSection
          taskId={id}
          question={escalationQuestion}
          escalationCreatedAt={escalationCreatedAt}
          onAction={onEscalationAction ? (action) => onEscalationAction(id, action) : undefined}
        />
      )}

      {(status === 'COMPLETED' || status === 'FAILED') && summary && (
        <p className={`task-summary${status === 'FAILED' ? ' task-summary--failed' : ''}`}>
          {summary}
        </p>
      )}
    </div>
  );
}
