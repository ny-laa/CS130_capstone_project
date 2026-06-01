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

function EscalationSection({ taskId, question, escalationCreatedAt }) {
  const countdown = useCountdown(escalationCreatedAt);
  const { updateTask } = useTasks();

  async function handle(action) {
    if (action === 'approve') {
      await approveEscalation(taskId);
      updateTask(taskId, { status: 'COMPLETED', summary: 'Escalation approved.' });
    } else {
      await denyEscalation(taskId);
      updateTask(taskId, { status: 'FAILED', summary: 'Escalation denied.' });
    }
  }

  return (
    <div className="escalation-section">
      <p className="escalation-question">{question}</p>
      <div className="escalation-footer">
        <span className="escalation-timer">Expires in {countdown}</span>
        <div className="escalation-actions">
          <button className="btn-approve" onClick={() => handle('approve')}>Approve</button>
          <button className="btn-deny" onClick={() => handle('deny')}>Deny</button>
        </div>
      </div>
    </div>
  );
}

export default function TaskCard({ task }) {
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
