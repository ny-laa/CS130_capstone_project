import { useState, useRef, useEffect, useCallback } from 'react';
import { sendMessage, parseTaskBlock } from '../api';
import { useTasks } from '../context/TaskContext';
import TypingIndicator from '../components/TypingIndicator';
import SuggestionPills from '../components/SuggestionPills';
import TaskSidebar from '../components/TaskSidebar';

// [GenAI Use] LLM Response Start
// iMessage-style chat page with 60/40 split layout. Calls Anthropic
// API and falls back to keyword-matched mock if no API key is set.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: The 60/40 split puts the chat on the left
// and task sidebar on the right. Verified the mock fallback works
// without VITE_ANTHROPIC_API_KEY set so the UI is usable in dev.
// Checked that task blocks parsed from AI responses get added to
// TaskContext via addTask so they appear in the sidebar and Tasks page.

const STATUS_MAP = {
  'Pending': 'PENDING',
  'In Progress': 'IN_PROGRESS',
  'Needs Approval': 'ESCALATION_PENDING',
};

const TASK_PILL_LABEL = {
  Reminder: '＋ Reminder added',
  Calendar: '＋ Calendar event added',
  Escalation: '＋ Escalation created',
};

function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function ChatMessage({ msg, onPillClick }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`chat-msg-row${isUser ? ' chat-msg-row--user' : ''}`}>
      {!isUser && <div className="chat-avatar">G</div>}
      <div className="chat-msg-body">
        <div className={`chat-bubble${isUser ? ' chat-bubble--user' : ' chat-bubble--g'}`}>
          <span>{msg.content}</span>
          {msg.task && (
            <button
              className={`task-pill task-pill--${msg.task.type.toLowerCase()}`}
              onClick={() => onPillClick(msg.task.id)}
            >
              {TASK_PILL_LABEL[msg.task.type] || '＋ Task added'}
            </button>
          )}
        </div>
        <div className="chat-msg-time">{formatTime(msg.timestamp)}</div>
      </div>
    </div>
  );
}

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const [conversationTaskIds, setConversationTaskIds] = useState([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const sidebarTaskRefs = useRef({});
  const { addTask } = useTasks();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  const send = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || typing) return;

    const userMsg = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
      task: null,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setTyping(true);

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    try {
      const apiMessages = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const raw = await sendMessage(apiMessages);
      const { cleanText, task: parsedTask } = parseTaskBlock(raw);

      let taskObj = null;
      if (parsedTask) {
        const taskId = `chat-task-${Date.now()}`;
        taskObj = {
          id: taskId,
          description: parsedTask.description || trimmed,
          type: parsedTask.type || 'Reminder',
          status: STATUS_MAP[parsedTask.status] || 'PENDING',
          createdAt: new Date().toISOString(),
          summary: parsedTask.summary || '',
        };
        addTask(taskObj);
        setConversationTaskIds((prev) => [...prev, taskId]);
        setDrawerOpen(true);
      }

      const assistantMsg = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: cleanText,
        timestamp: Date.now(),
        task: taskObj ? { ...taskObj } : null,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errMsg = {
        id: `msg-${Date.now() + 1}`,
        role: 'assistant',
        content: "Sorry, I had trouble connecting. Please try again in a moment.",
        timestamp: Date.now(),
        task: null,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setTyping(false);
    }
  }, [messages, typing, addTask]);

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  function scrollToTask(taskId) {
    const el = sidebarTaskRefs.current[taskId];
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    if (window.innerWidth <= 768) setDrawerOpen(true);
  }

  return (
    <div className="chat-page">
      <div className="chat-panel">
        <div className="chat-header">
          <div className="chat-header-avatar">G</div>
          <div className="chat-header-info">
            <h2>G</h2>
            <p>Your AI secretary</p>
          </div>
        </div>

        <div className="chat-messages">
          {messages.length === 0 ? (
            <SuggestionPills onSelect={send} />
          ) : (
            <>
              {messages.map((msg) => (
                <ChatMessage key={msg.id} msg={msg} onPillClick={scrollToTask} />
              ))}
              {typing && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        <div className="chat-input-bar">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder="Message G…"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={typing}
          />
          <button
            className="chat-send-btn"
            onClick={() => send(input)}
            disabled={!input.trim() || typing}
            aria-label="Send"
          >
            ↑
          </button>
        </div>
      </div>

      <TaskSidebar
        taskIds={conversationTaskIds}
        drawerOpen={drawerOpen}
        onDrawerToggle={() => setDrawerOpen((o) => !o)}
      />
    </div>
  );
}
