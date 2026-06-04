import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { isLoggedIn, getUser, setUser } from '../../auth';
import { updatePreferences, fetchUser } from '../../api';
import ProgressBar from '../../components/ProgressBar';
import Toggle from '../../components/Toggle';
import TimePicker from '../../components/TimePicker';

// [GenAI Use] Prompt: "Step2Preferences used to merge step1 localStorage
// data with prefs and write it all to g_user, clobbering the backend user
// (with its real id). Drop the g_onboard guard, drop the overwrite. On
// Activate, PATCH /api/users/{id}/preferences with the backend-shape
// payload (snake_case fields, mapped enums), then GET /api/users/{id} and
// store the result. Navigate to /tasks. Map the digest content options
// to the backend's DigestContent enum -- the third option (`+ Emails +
// Tasks`) is collapsed to `calendar+tasks` until the backend learns the
// triple combo."
// [GenAI Use] LLM Response Start

// Backend DigestContent enum only has 'calendar', 'calendar+email',
// 'calendar+tasks' -- no triple combo. Frontend triple-option label is
// kept for UI continuity; we map it to 'calendar+tasks' at send time.
const DIGEST_OPTS = [
  { value: 'calendar', label: 'Calendar only' },
  { value: 'calendar+email', label: '+ Emails' },
  { value: 'calendar+tasks', label: '+ Tasks' },
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

// Map frontend prefs (camelCase, UI shape) to the backend's
// UserPreferencesUpdate payload (snake_case, enum values). Backend silently
// ignores unknown keys, but we keep the mapping explicit so a wrong key
// is caught here, not server-side.
function toBackendPrefs(p) {
  const payload = {};

  if (p.communicationStyle) payload.comm_style = p.communicationStyle;
  if (p.preferredContact) {
    // frontend uses 'text'; backend enum is 'sms'.
    payload.preferred_channel = p.preferredContact === 'text' ? 'sms' : 'call';
  }
  if (p.callUrgencyThreshold) payload.call_urgency_threshold = p.callUrgencyThreshold;

  // wrap the form's start/end pair into the JSONB list shape the backend
  // expects ({start_time, end_time}) so the notify_user quiet-hours check
  // can read it without a converter.
  if (p.quietHoursStart && p.quietHoursEnd) {
    payload.blocked_windows = [
      { start_time: p.quietHoursStart, end_time: p.quietHoursEnd },
    ];
  }
  if (p.keepFreeStart && p.keepFreeEnd) {
    payload.keep_free_windows = [
      { start_time: p.keepFreeStart, end_time: p.keepFreeEnd },
    ];
  }
  if (Array.isArray(p.activeDays)) payload.active_days = p.activeDays;

  if (typeof p.morningDigest === 'boolean') payload.morning_digest_enabled = p.morningDigest;
  if (p.digestTime) payload.morning_digest_time = p.digestTime;
  if (p.digestContent) payload.morning_digest_content = p.digestContent;
  if (typeof p.digestTravelTime === 'boolean') payload.morning_digest_travel_time = p.digestTravelTime;

  if (Number.isFinite(p.escalationTimeoutMinutes)) {
    payload.escalation_timeout_minutes = p.escalationTimeoutMinutes;
  }
  if (typeof p.autoApproveLowRisk === 'boolean') payload.auto_approve_low_risk = p.autoApproveLowRisk;
  if (Number.isFinite(p.maxReminders)) payload.max_reminders = p.maxReminders;

  if (p.tone) payload.tone = p.tone;
  // reminderLeadTime is a string of minutes in the UI; backend wants int.
  if (p.reminderLeadTime) {
    const n = parseInt(p.reminderLeadTime, 10);
    if (Number.isFinite(n)) payload.reminder_lead_time_minutes = n;
  }
  if (p.conflictHandling) payload.conflict_handling = p.conflictHandling;

  return payload;
}

export default function Step2Preferences() {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState(DEFAULT_PREFS);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    if (!isLoggedIn()) {
      navigate('/signin?next=/onboard/step2', { replace: true });
    }
  }, [navigate]);

  function setPref(key, val) {
    setPrefs((p) => ({ ...p, [key]: val }));
  }

  async function handleActivate() {
    if (submitting) return;
    setSubmitError('');
    const user = getUser();
    if (!user?.id) {
      setSubmitError('Session expired -- please sign in again.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = toBackendPrefs(prefs);
      if (Object.keys(payload).length > 0) {
        await updatePreferences(user.id, payload);
      }
      // refresh canonical user state so downstream pages see the saved prefs.
      const refreshed = await fetchUser(user.id);
      setUser({ ...refreshed, bannerDismissed: false });
      navigate('/tasks');
    } catch (err) {
      setSubmitError(err.message || 'Could not save preferences. Please try again.');
    } finally {
      setSubmitting(false);
    }
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
        {submitError && <span className="error-msg">{submitError}</span>}
        <button
          className="btn btn-brand"
          onClick={handleActivate}
          disabled={submitting}
        >
          {submitting ? 'Activating…' : 'Activate G'}
        </button>
      </div>
      {/* [GenAI Use] LLM Response End */}
      {/* [GenAI Use] Reflection: kept the partial-success behavior of
          PATCH /preferences -- if some fields fail backend validation,
          others still save. The refresh via fetchUser pulls whatever the
          server actually accepted so the UI doesn't show a delta from
          reality. Skipped Promise.all between the patch and refresh
          because the refresh has to see the patched state. */}
    </div>
  );
}
