import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { setUser } from '../../auth';
import ProgressBar from '../../components/ProgressBar';
import Toggle from '../../components/Toggle';
import TimePicker from '../../components/TimePicker';

// [GenAI Use] LLM Response Start
// All preference toggles. "Activate G" logs payload, saves merged 
// data to g_user, navigates to /profile
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: On "Activate G" click, this step merges 
// g_onboard data from step 1 with preferences from step 2 into a 
// single object and saves to g_user via setUser() from auth.js. 
// The g_onboard key is then no longer needed. Verified the payload 
// is logged to console which is useful for debugging before real 
// backend is connected. Confirmed NavBar is hidden on /onboard/* 
// routes per App.jsx.

const DIGEST_OPTS = [
  { value: 'calendar', label: 'Calendar only' },
  { value: 'calendar+email', label: '+ Emails' },
  { value: 'calendar+email+tasks', label: '+ Emails + Tasks' },
];

const REMINDER_OPTS = [
  { value: '15', label: '15 min' },
  { value: '30', label: '30 min' },
  { value: '60', label: '1 hour' },
  { value: '1440', label: '1 day' },
];

const ESCALATION_OPTS = [
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 60, label: '60 min' },
];

const DEFAULT_PREFS = {
  communicationStyle: 'brief',
  preferredContact: 'text',
  tone: 'casual',
  morningDigest: false,
  digestTime: '07:00',
  digestContent: 'calendar',
  digestTravelTime: false,
  keepFreeStart: '',
  keepFreeEnd: '',
  quietHoursStart: '22:00',
  quietHoursEnd: '07:00',
  reminderLeadTime: '30',
  autoApproveLowRisk: false,
  escalationTimeoutMinutes: 30,
  activeDays: ['mon', 'tue', 'wed', 'thu', 'fri'],
  callUrgencyThreshold: 'high',
  maxReminders: 3,
  conflictHandling: 'suggest',
};

export default function Step2Preferences() {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);

  useEffect(() => {
    if (!localStorage.getItem('g_onboard')) navigate('/signup', { replace: true });
  }, [navigate]);

  function setPref(key, val) {
    setPrefs((p) => ({ ...p, [key]: val }));
  }

  function handleActivate() {
    const step1 = JSON.parse(localStorage.getItem('g_onboard') || '{}');
    const user = { ...step1, preferences: prefs, bannerDismissed: false };
    console.log('G activation payload:', user);
    setUser(user);
    localStorage.removeItem('g_onboard');
    navigate('/profile');
  }

  return (
    <div className="onboard-page">
      <ProgressBar current={2} total={2} />
      <h1 className="onboard-title">Your preferences</h1>

      {/* Communication */}
      <section className="card">
        <h2 className="card-title">Communication</h2>

        <div className="pref-row">
          <span className="pref-label">Style</span>
          <div className="pref-choice">
            <button className={`choice-btn ${prefs.communicationStyle === 'brief' ? 'active' : ''}`} onClick={() => setPref('communicationStyle', 'brief')}>Brief</button>
            <button className={`choice-btn ${prefs.communicationStyle === 'detailed' ? 'active' : ''}`} onClick={() => setPref('communicationStyle', 'detailed')}>Detailed</button>
          </div>
        </div>

        <div className="pref-row">
          <span className="pref-label">Method</span>
          <div className="pref-choice">
            <button className={`choice-btn ${prefs.preferredContact === 'text' ? 'active' : ''}`} onClick={() => setPref('preferredContact', 'text')}>Text</button>
            <button className={`choice-btn ${prefs.preferredContact === 'call' ? 'active' : ''}`} onClick={() => setPref('preferredContact', 'call')}>Call</button>
          </div>
        </div>

        <div className="pref-row">
          <span className="pref-label">Tone</span>
          <div className="pref-choice">
            <button className={`choice-btn ${prefs.tone === 'formal' ? 'active' : ''}`} onClick={() => setPref('tone', 'formal')}>Formal</button>
            <button className={`choice-btn ${prefs.tone === 'casual' ? 'active' : ''}`} onClick={() => setPref('tone', 'casual')}>Casual</button>
          </div>
        </div>
      </section>

      {/* Morning Digest */}
      <section className="card">
        <h2 className="card-title">Morning Digest</h2>

        <Toggle label="Send morning digest" checked={prefs.morningDigest} onChange={(v) => setPref('morningDigest', v)} />

        {prefs.morningDigest && (
          <>
            <div className="pref-row">
              <span className="pref-label">Time</span>
              <TimePicker label="" value={prefs.digestTime} onChange={(v) => setPref('digestTime', v)} />
            </div>
            <div className="pref-row pref-row--block">
              <span className="pref-label">Include</span>
              <div className="pill-options">
                {DIGEST_OPTS.map((o) => (
                  <button key={o.value} className={`pill-btn ${prefs.digestContent === o.value ? 'active' : ''}`} onClick={() => setPref('digestContent', o.value)}>{o.label}</button>
                ))}
              </div>
            </div>
          </>
        )}
      </section>

      {/* Timing */}
      <section className="card">
        <h2 className="card-title">Timing</h2>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Keep-free window</span>
          <div className="time-range">
            <TimePicker label="From" value={prefs.keepFreeStart} onChange={(v) => setPref('keepFreeStart', v)} />
            <TimePicker label="To" value={prefs.keepFreeEnd} onChange={(v) => setPref('keepFreeEnd', v)} />
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Quiet hours</span>
          <div className="time-range">
            <TimePicker label="From" value={prefs.quietHoursStart} onChange={(v) => setPref('quietHoursStart', v)} />
            <TimePicker label="To" value={prefs.quietHoursEnd} onChange={(v) => setPref('quietHoursEnd', v)} />
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Reminder lead time</span>
          <div className="pill-options">
            {REMINDER_OPTS.map((o) => (
              <button key={o.value} className={`pill-btn ${prefs.reminderLeadTime === o.value ? 'active' : ''}`} onClick={() => setPref('reminderLeadTime', o.value)}>{o.label}</button>
            ))}
          </div>
        </div>
      </section>

      {/* Escalation */}
      <section className="card">
        <h2 className="card-title">Escalation</h2>

        <Toggle label="Auto-approve low-risk actions" checked={prefs.autoApproveLowRisk} onChange={(v) => setPref('autoApproveLowRisk', v)} />

        <div className="pref-row pref-row--block">
          <span className="pref-label">Escalation timeout</span>
          <div className="pill-options">
            {ESCALATION_OPTS.map((o) => (
              <button key={o.value} className={`pill-btn ${prefs.escalationTimeoutMinutes === o.value ? 'active' : ''}`} onClick={() => setPref('escalationTimeoutMinutes', o.value)}>{o.label}</button>
            ))}
          </div>
        </div>
      </section>

      <div className="onboard-footer">
        <button className="btn btn-brand" onClick={handleActivate}>Activate G</button>
      </div>
    </div>
  );
}
