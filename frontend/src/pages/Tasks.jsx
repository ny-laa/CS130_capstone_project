import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getTasks } from '../api';
import { getUser } from '../auth';
import TaskCard from '../components/TaskCard';

// [GenAI Use] Prompt: "Tasks.jsx used to read from a localStorage-backed
// TaskContext mock. Replace with a real fetch of GET /api/users/{id}/tasks.
// Backend returns TaskResponse rows ({id, status, type, description,
// plan_steps, created_at, ...}); TaskCard expects {id, description, type,
// status, createdAt, summary}. Title-case the lowercase enum 'type' for
// the badge, derive a summary from the first plan_step's body/message for
// completed/failed rows. Show loading / error / empty states. Redirect to
// /signin if no user."
// [GenAI Use] LLM Response Start

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
  const [tasks, setTasks] = useState([]);
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
        setTasks(rows.map(toCardTask));
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
      {!loading && !error && tasks.length === 0 && (
        <p className="task-empty">No tasks yet. Text or chat G to schedule one.</p>
      )}
      <div className="task-list">
        {tasks.map((t) => (
          <TaskCard key={t.id} task={t} />
        ))}
      </div>
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: kept the response-shape mapping in a pure
// helper (toCardTask) so when the escalation engine adds
// escalationQuestion / escalationCreatedAt fields, they can flow through
// the same mapper. cancelled flag in the useEffect cleanup prevents a
// state update on an unmounted component if the user navigates away
// mid-fetch.
