import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTasks } from '../api';
import { getUser } from '../auth';
import TaskCard from '../components/TaskCard';

// [GenAI Use] Prompt: "Tasks.jsx fetches every Task row the backend
// returns, including COMPLETED reminders that already fired -- those
// shouldn't surface here since the resulting outbound message already
// shows in History. Split rendering into two groups: Active (PENDING /
// IN_PROGRESS / ESCALATION_PENDING) at the top, and Issues (FAILED)
// collapsed at the bottom so the user notices broken reminders. Drop
// COMPLETED entirely from the dashboard."
// [GenAI Use] LLM Response Start

// Statuses that represent "G's active to-do list" -- shown at the top.
// COMPLETED is intentionally omitted: the outbound message that fulfilled
// the task already lives in History.
const ACTIVE_STATUSES = new Set(['PENDING', 'IN_PROGRESS', 'ESCALATION_PENDING']);
// Things G tried and couldn't do -- bubble up as Issues so they get noticed.
const ISSUE_STATUSES = new Set(['FAILED']);

function titleCase(s) {
  if (!s) return '';
  return s
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function toCardTask(t) {
  const firstStep = Array.isArray(t.plan_steps) ? t.plan_steps[0] : null;
  const stepParams = firstStep?.params || {};
  const stepMessage = stepParams.body || stepParams.message || '';

  let summary = null;
  if (t.status === 'COMPLETED' && stepMessage) summary = `Sent: "${stepMessage}"`;
  else if (t.status === 'FAILED') summary = 'Delivery failed. Check logs.';

  return {
    id: t.id,
    description: t.description,
    type: titleCase(t.type),
    status: t.status,
    createdAt: t.created_at,
    summary,
  };
}

export default function Tasks() {
  const navigate = useNavigate();
  const [active, setActive] = useState([]);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const user = getUser();
    if (!user?.id) {
      navigate('/signin?next=/tasks', { replace: true });
      return;
    }
    let cancelled = false;
    getTasks(user.id)
      .then((rows) => {
        if (cancelled) return;
        const cards = rows.map(toCardTask);
        setActive(cards.filter((t) => ACTIVE_STATUSES.has(t.status)));
        setIssues(cards.filter((t) => ISSUE_STATUSES.has(t.status)));
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || 'Failed to load tasks');
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [navigate]);

  return (
    <div className="page">
      <h1 className="page-title">Task Dashboard</h1>
      {loading && <p className="task-empty">Loading…</p>}
      {!loading && error && <p className="error-msg">{error}</p>}
      {!loading && !error && active.length === 0 && issues.length === 0 && (
        <p className="task-empty">No tasks yet. Text or chat G to schedule one.</p>
      )}

      {active.length > 0 && (
        <div className="task-list">
          {active.map((t) => (
            <TaskCard key={t.id} task={t} />
          ))}
        </div>
      )}

      {issues.length > 0 && (
        <>
          <h2 className="section-title" style={{ marginTop: 32 }}>
            Issues ({issues.length})
          </h2>
          <p className="card-description" style={{ marginBottom: 12 }}>
            These tasks didn't complete successfully. G couldn't deliver, or something else went wrong.
          </p>
          <div className="task-list">
            {issues.map((t) => (
              <TaskCard key={t.id} task={t} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: kept COMPLETED rows in the DB on purpose --
// they're still useful as the parent record that a Message in History
// belongs to (via Message.task_id), and a future "show all tasks ever"
// admin view can re-include them. The dashboard's job is "what G is
// working on right now"; the History tab's job is "what G has done".
// Filtering at render time instead of via a ?status=active query keeps
// the backend endpoint simple and means switching the policy is a
// one-line frontend edit.
