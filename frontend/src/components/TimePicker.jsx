// [GenAI Use] LLM Response Start
// Labeled <input type="time"> wrapper component
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Confirmed e.target.value returns "HH:MM" 
// string as expected. Verified input type="time" browser support:
// https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/time

export default function TimePicker({ value, onChange, label }) {
  return (
    <label className="field-group">
      <span className="field-label">{label}</span>
      <input
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="time-input"
      />
    </label>
  );
}
