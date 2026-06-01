// [GenAI Use] LLM Response Start
// Step progress fill bar
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Takes current step and total steps as props
// and computes fill percentage as (step/total) * 100. Straightforward
// visual component. Verified it shows correct progress on both step 1 
// and step 2 of onboarding.

export default function ProgressBar({ current, total }) {
  return (
    <div className="progress-bar-wrapper">
      <div className="progress-bar">
        <div className="progress-bar-fill" style={{ width: `${(current / total) * 100}%` }} />
      </div>
      <p className="progress-label">Step {current} of {total}</p>
    </div>
  );
}
