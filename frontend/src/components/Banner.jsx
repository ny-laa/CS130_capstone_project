// [GenAI Use] LLM Response Start
// Dismissable top banner component
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Banner is shown on first visit to /profile
// after onboarding completes. Dismiss sets a flag in localStorage so 
// it does not reappear on refresh. Simple presentational component 
// that takes a message prop. Verified it renders correctly above 
// profile content.

export default function Banner({ message, onDismiss }) {
  return (
    <div className="banner">
      <span className="banner-message">{message}</span>
      <button className="banner-dismiss" onClick={onDismiss} aria-label="Dismiss">✕</button>
    </div>
  );
}
