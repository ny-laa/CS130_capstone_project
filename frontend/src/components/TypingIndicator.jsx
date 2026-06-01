export default function TypingIndicator() {
  return (
    <div className="chat-msg-row">
      <div className="chat-avatar">G</div>
      <div className="typing-indicator">
        <div className="typing-dot" />
        <div className="typing-dot" />
        <div className="typing-dot" />
      </div>
    </div>
  );
}

// [GenAI Use] LLM Response Start
// 3 animated dots inside a G bubble shown while waiting for a response
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Dots use CSS animation with staggered delays
// so they bounce one at a time. Shows while API call is in flight and
// disappears when the response arrives. Checked the animation looks
// smooth and does not flicker.

