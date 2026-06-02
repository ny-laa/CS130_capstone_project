import TaskCard from '../components/TaskCard';
import { useTasks } from '../context/TaskContext';

// [GenAI Use] LLM Response Start
// Now reads from TaskContext instead of mock API so chat-created
// tasks show up instantly.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: This was the key change to make chat and
// tasks feel connected. Before this, tasks page used its own mock
// data. Now it shares the same source of truth as the chat sidebar.

export default function Tasks() {
  const { tasks } = useTasks();

  return (
    <div className="page">
      <h1 className="page-title">Task Dashboard</h1>
      <div className="task-list">
        {tasks.map((t) => (
          <TaskCard key={t.id} task={t} />
        ))}
      </div>
    </div>
  );
}
