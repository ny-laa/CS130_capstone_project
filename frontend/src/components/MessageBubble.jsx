function formatTime(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// [GenAI Use] LLM Response Start
// Chat bubble with inbound/outbound direction, channel, badge
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Verified direction string matches mock data.
// Consulted toLocaleTimeString for timestamp formatting:
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date/toLocaleTimeString

export default function MessageBubble({ message }) {
  const { direction, channel, content, timestamp, taskCreated } = message;
  const isUser = direction === 'inbound';

  return (
    <div className={`bubble-row ${isUser ? 'bubble-row--user' : 'bubble-row--g'}`}>
      {!isUser && <div className="bubble-avatar">G</div>}
      <div className="bubble-body">
        <div className={`bubble ${isUser ? 'bubble--user' : 'bubble--g'}`}>
          <span>{content}</span>
          {taskCreated && <span className="task-badge">Task created</span>}
        </div>
        <div className="bubble-meta">
          {formatTime(timestamp)} · {channel.toUpperCase()}
        </div>
      </div>
    </div>
  );
}
