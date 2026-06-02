import { Link } from 'react-router-dom';
import { useTasks } from '../context/TaskContext';

// [GenAI Use] LLM Response Start
// Right panel showing tasks created in the current conversation.
// Approve/Deny buttons update TaskContext immediately.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Approve and Deny call updateTask from context
// so the status change shows up on the Tasks page too without a reload.
// Sidebar has a slide-in animation on mobile as a drawer. Checked that
// only tasks from the current conversation are shown here, not all tasks.

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

function SidebarTaskCard({ task }) {
  const { updateTask } = useTasks();
  const { id, description, type, status } = task;

  function approve() {
    updateTask(id, { status: 'COMPLETED', summary: 'Approved via chat.' });
  }

  function deny() {
    updateTask(id, { status: 'FAILED', summary: 'Denied via chat.' });
  }

  return (
    <div className="sidebar-task-card">
      <p className="sidebar-task-desc">{description}</p>
      <div className="sidebar-task-badges">
        <span className="badge badge-type">{type}</span>
        <span className="badge badge-status" style={{ background: STATUS_COLORS[status] }}>
          {STATUS_LABELS[status]}
        </span>
      </div>
      {status === 'ESCALATION_PENDING' && (
        <div className="sidebar-task-actions">
          <button className="btn-approve" onClick={approve}>Approve</button>
          <button className="btn-deny" onClick={deny}>Deny</button>
        </div>
      )}
      <Link to="/tasks" className="sidebar-dashboard-link">View in Dashboard →</Link>
    </div>
  );
}

export default function TaskSidebar({ taskIds, drawerOpen, onDrawerToggle }) {
  const { tasks } = useTasks();
  const sidebarTasks = tasks.filter((t) => taskIds.includes(t.id));

  return (
    <aside className={`chat-sidebar${drawerOpen ? ' chat-sidebar--open' : ''}`}>
      <div className="chat-drawer-handle" onClick={onDrawerToggle} />
      <div className="sidebar-header">
        <h3>Tasks from this conversation ({sidebarTasks.length})</h3>
      </div>
      <div className="sidebar-tasks">
        {sidebarTasks.length === 0 ? (
          <p className="sidebar-empty">Tasks created in this conversation will appear here.</p>
        ) : (
          sidebarTasks.map((t) => <SidebarTaskCard key={t.id} task={t} />)
        )}
      </div>
    </aside>
  );
}
