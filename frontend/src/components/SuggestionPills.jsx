const SUGGESTIONS = [
  "Remind me to pick up Emma from soccer at 4pm",
  "Schedule a dentist appointment for next week",
  "What's on my calendar tomorrow?",
];

// [GenAI Use] LLM Response Start
// 3 tappable starter messages shown when chat is empty
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Pills disappear once the user sends a message.
// Each pill fills the input with a preset message so users know what
// kinds of things they can ask. Good for first-time users.

export default function SuggestionPills({ onSelect }) {
  return (
    <div className="suggestion-pills">
      <div className="suggestion-pills-intro">
        <div className="suggestion-g-icon">G</div>
        <p>How can I help you today?</p>
        <span>Tap a suggestion or type your own message</span>
      </div>
      <div className="suggestion-pills-list">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="suggestion-pill" onClick={() => onSelect(s)}>
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
