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

// If a PENDING task's scheduled_at is more than this far in the past,
// we treat it as failed for display. Tasks that were scheduled but the
// Celery worker never ran (or was offline at the time) pile up as
// PENDING in the DB; without this they'd look like active to-dos
// forever. 5 min slack absorbs the normal eta tolerance + brief worker
// downtime.
const PAST_DUE_GRACE_MS = 5 * 60 * 1000;

// Issues older than this stop appearing on the dashboard. Row stays in
// the DB (History still references it via task_id), it's just hidden so
// the Issues group doesn't pile up dead weight indefinitely.
const ISSUE_VISIBLE_MS = 24 * 60 * 60 * 1000;

function toCardTask(t) {
  const firstStep = Array.isArray(t.plan_steps) ? t.plan_steps[0] : null;
  const stepParams = firstStep?.params || {};
  const stepMessage = stepParams.body || stepParams.message || '';

  // Past-due PENDING -> display as FAILED so it bubbles into the Issues
  // group. DB stays at PENDING (truthful: maybe the worker will catch
  // up); this is a render-time override only.
  let displayStatus = t.status;
  let pastDue = false;
  if (t.status === 'PENDING' && stepParams.scheduled_at) {
    const scheduledMs = Date.parse(stepParams.scheduled_at);
    if (!Number.isNaN(scheduledMs) && Date.now() - scheduledMs > PAST_DUE_GRACE_MS) {
      displayStatus = 'FAILED';
      pastDue = true;
    }
  }

  let summary = null;
  if (pastDue) summary = 'Scheduled time passed without firing. Worker may have been offline.';
  else if (t.status === 'COMPLETED' && stepMessage) summary = `Sent: "${stepMessage}"`;
  else if (t.status === 'FAILED') summary = 'Delivery failed. Check logs.';

  // Pick the "last activity" timestamp for age-out filtering. For genuine
  // FAILED tasks updated_at is the failure time. For past-due PENDING that
  // we're rendering as FAILED, scheduled_at is what matters (updated_at
  // equals created_at, i.e. when the user scheduled it).
  const lastActivityIso = pastDue && stepParams.scheduled_at
    ? stepParams.scheduled_at
    : (t.updated_at || t.created_at);

  // For ESCALATION_PENDING tasks, derive a countdown start from the stored deadline.
  // TaskCard adds 30 min to escalationCreatedAt to compute the expiry, so we pass
  // deadline - 30min to make that math land on the real deadline.
  let escalationQuestion = null;
  let escalationCreatedAt = null;
  if (displayStatus === 'ESCALATION_PENDING') {
    escalationQuestion = t.escalation_question || 'G needs your approval to proceed. Approve or Deny.';
    escalationCreatedAt = t.escalation_deadline
      ? new Date(Date.parse(t.escalation_deadline) - 30 * 60 * 1000).toISOString()
      : (t.updated_at || t.created_at);
  }

  return {
    id: t.id,
    description: t.description,
    type: titleCase(t.type),
    status: displayStatus,
    createdAt: t.created_at,
    lastActivityIso,
    summary,
    escalationQuestion,
    escalationCreatedAt,
  };
}

export default function Tasks() {
  const navigate = useNavigate();
  const [active, setActive] = useState([]);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  function handleEscalationAction(taskId, action) {
    setActive((prev) => prev.filter((t) => t.id !== taskId));
    if (action !== 'approve') {
      const task = active.find((t) => t.id === taskId);
      if (task) {
        setIssues((prev) => [
          { ...task, status: 'FAILED', summary: 'Escalation denied.', lastActivityIso: new Date().toISOString() },
          ...prev,
        ]);
      }
    }
  }

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
        // Issues age out after 24h so the dashboard doesn't accumulate
        // dead weight. The Task row is still in the DB; this is just
        // a display filter.
        const cutoff = Date.now() - ISSUE_VISIBLE_MS;
        setIssues(
          cards.filter((t) => {
            if (!ISSUE_STATUSES.has(t.status)) return false;
            const ageMs = Date.parse(t.lastActivityIso);
            return Number.isNaN(ageMs) ? true : ageMs >= cutoff;
          })
        );
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
            <TaskCard key={t.id} task={t} onEscalationAction={handleEscalationAction} />
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
