import { createContext, useContext, useState, useEffect } from 'react';

// [GenAI Use] LLM Response Start
// React context seeded with mock tasks, persists to localStorage.
// addTask and updateTask shared across the whole app.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Checked that addTask and updateTask both
// save to localStorage so tasks survive a page refresh. Context wraps
// the whole app in App.jsx so any page can read or update tasks.
// This is why chat-created tasks show up on the Tasks page instantly.

const TaskContext = createContext(null);
const STORAGE_KEY = 'g_tasks';

const INITIAL_TASKS = [
  {
    id: 'task-001',
    description: 'Remind me to pick up Mark at 4pm today',
    type: 'Reminder',
    status: 'COMPLETED',
    createdAt: '2026-05-24T15:02:00Z',
    summary: "Sent reminder at 3:55 PM: \"Heads up — it's almost 4 PM! Time to pick up Mark.\"",
  },
  {
    id: 'task-002',
    description: 'Schedule a dentist appointment for Emma next week after 3pm',
    type: 'Calendar',
    status: 'ESCALATION_PENDING',
    createdAt: '2026-05-24T15:03:45Z',
    escalationQuestion:
      'I found an opening at Westside Dental on Tuesday May 28 at 3:30 PM. Should I confirm this appointment?',
    escalationCreatedAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
  {
    id: 'task-003',
    description: 'Call the insurance company about the claim from last month',
    type: 'Escalation',
    status: 'IN_PROGRESS',
    createdAt: '2026-05-24T09:15:00Z',
  },
  {
    id: 'task-004',
    description: "Order more of Sarah's blood pressure medication from the pharmacy",
    type: 'Reminder',
    status: 'PENDING',
    createdAt: '2026-05-24T11:30:00Z',
  },
  {
    id: 'task-005',
    description: 'Find a plumber to fix the leak under the kitchen sink',
    type: 'Escalation',
    status: 'FAILED',
    createdAt: '2026-05-23T14:00:00Z',
    summary: 'Unable to reach any available plumbers in the area. Please try calling directly.',
  },
];

export function TaskProvider({ children }) {
  const [tasks, setTasks] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return INITIAL_TASKS;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  }, [tasks]);

  function addTask(task) {
    setTasks((prev) => [task, ...prev]);
  }

  function updateTask(id, updates) {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, ...updates } : t)));
  }

  return (
    <TaskContext.Provider value={{ tasks, addTask, updateTask }}>
      {children}
    </TaskContext.Provider>
  );
}

export function useTasks() {
  const ctx = useContext(TaskContext);
  if (!ctx) throw new Error('useTasks must be used within TaskProvider');
  return ctx;
}
