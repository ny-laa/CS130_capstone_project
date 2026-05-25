export default function Toggle({ checked, onChange, label }) {
  return (
    <label className="toggle-wrapper" onClick={() => onChange(!checked)}>
      <span className="toggle-label">{label}</span>
      <div className={`toggle ${checked ? 'on' : 'off'}`}>
        <div className="toggle-thumb" />
      </div>
    </label>
  );
}
