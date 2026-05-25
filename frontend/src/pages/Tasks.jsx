import { useState, useEffect } from 'react';
import { getTasks } from '../api';
import TaskCard from '../components/TaskCard';

export default function Tasks() {
  const [tasks, setTasks] = useState([]);

  useEffect(() => {
    getTasks().then(setTasks);
  }, []);

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
