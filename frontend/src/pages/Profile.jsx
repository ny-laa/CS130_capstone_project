import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { isLoggedIn, getUser as getCachedUser, setUser as cacheUser } from '../auth';
import {
  fetchUser,
  updateProfile,
  updatePreferences,
  listFamilyMembers,
  createFamilyMember,
  deleteFamilyMember,
  listContacts,
  createContact,
  deleteContact,
  listProviders,
  createProvider,
  deleteProvider,
} from '../api';
import Toggle from '../components/Toggle';
import TimePicker from '../components/TimePicker';
import Banner from '../components/Banner';

// [GenAI Use] Prompt: "Profile.jsx used to read a hand-crafted mock user
// object from localStorage with nested .preferences, .familyMembers,
// .contacts, .providers. The real backend returns a flat snake_case
// UserResponse and serves family/contacts/providers from separate list
// endpoints. Rewrite: on mount fetch user + 3 lists in parallel, map
// backend shape into the form state the existing JSX expects, sync
// family/contact/provider add+remove through their POST/DELETE endpoints
// immediately (no batch save for those), and on Save PATCH preferences
// (mapped to UserPreferencesUpdate shape) + PATCH profile if email
// changed, then refetch. Keep all the existing rendering as-is."
// [GenAI Use] LLM Response Start

const DAYS = [
  { key: 'mon', label: 'M' },
  { key: 'tue', label: 'Tu' },
  { key: 'wed', label: 'W' },
  { key: 'thu', label: 'Th' },
  { key: 'fri', label: 'F' },
  { key: 'sat', label: 'Sa' },
  { key: 'sun', label: 'Su' },
];

// Backend UserResponse -> form-shaped prefs the existing JSX reads.
// Defaults are picked to match what onboarding step 2 uses so a fresh
// account (where most fields are null) renders sane buttons.
function prefsFromBackend(u) {
  const blocked = Array.isArray(u.blocked_windows) ? u.blocked_windows[0] : null;
  const keepFree = Array.isArray(u.keep_free_windows) ? u.keep_free_windows[0] : null;

  return {
    communicationStyle: u.comm_style || 'brief',
    // backend uses 'sms' (matches the message channel enum); UI calls it 'text'.
    preferredContact: u.preferred_channel === 'call' ? 'call' : 'text',
    callUrgencyThreshold: u.call_urgency_threshold || 'high',

    quietHoursStart: blocked?.start_time || '22:00',
    quietHoursEnd: blocked?.end_time || '07:00',
    keepFreeStart: keepFree?.start_time || '',
    keepFreeEnd: keepFree?.end_time || '',
    activeDays: Array.isArray(u.active_days) ? u.active_days : ['mon', 'tue', 'wed', 'thu', 'fri'],

    morningDigest: !!u.morning_digest_enabled,
    digestTime: u.morning_digest_time || '07:00',
    digestContent: u.morning_digest_content || 'calendar',
    digestTravelTime: !!u.morning_digest_travel_time,

    escalationTimeoutMinutes: u.escalation_timeout_minutes ?? 30,
    autoApproveLowRisk: !!u.auto_approve_low_risk,
    maxReminders: u.max_reminders ?? 3,

    tone: u.tone || 'casual',
    reminderLeadTime: String(u.reminder_lead_time_minutes ?? 30),
    conflictHandling: u.conflict_handling || 'suggest',
  };
}

// Reverse mapping for Save. Only includes fields the user could have
// changed via the UI -- everything else stays at its backend value.
function prefsToBackend(p) {
  return {
    comm_style: p.communicationStyle,
    preferred_channel: p.preferredContact === 'text' ? 'sms' : 'call',
    call_urgency_threshold: p.callUrgencyThreshold,
    blocked_windows:
      p.quietHoursStart && p.quietHoursEnd
        ? [{ start_time: p.quietHoursStart, end_time: p.quietHoursEnd }]
        : null,
    keep_free_windows:
      p.keepFreeStart && p.keepFreeEnd
        ? [{ start_time: p.keepFreeStart, end_time: p.keepFreeEnd }]
        : null,
    active_days: p.activeDays,
    morning_digest_enabled: p.morningDigest,
    morning_digest_time: p.digestTime,
    morning_digest_content: p.digestContent,
    morning_digest_travel_time: p.digestTravelTime,
    escalation_timeout_minutes: p.escalationTimeoutMinutes,
    auto_approve_low_risk: p.autoApproveLowRisk,
    max_reminders: p.maxReminders,
    tone: p.tone,
    reminder_lead_time_minutes: parseInt(p.reminderLeadTime, 10) || 30,
    conflict_handling: p.conflictHandling,
  };
}

export default function Profile() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [prefs, setPrefs] = useState(null);
  const [familyMembers, setFamilyMembers] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [newMember, setNewMember] = useState({ name: '', relation: '', phone_number: '' });
  const [newContact, setNewContact] = useState({ name: '', role: '', org: '', phone: '' });
  const [newProvider, setNewProvider] = useState({ name: '', specialty: '', practice: '' });

  const userId = getCachedUser()?.id;

  useEffect(() => {
    if (!isLoggedIn() || !userId) {
      navigate('/signin?next=/profile', { replace: true });
      return;
    }
    let cancelled = false;
    Promise.all([
      fetchUser(userId),
      listFamilyMembers(userId),
      listContacts(userId),
      listProviders(userId),
    ])
      .then(([u, fam, cts, prov]) => {
        if (cancelled) return;
        setUser(u);
        setPrefs(prefsFromBackend(u));
        setFamilyMembers(fam || []);
        setContacts(cts || []);
        setProviders(prov || []);
        // refresh cached user so other pages see the latest snapshot
        cacheUser(u);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err.message || 'Could not load your profile.');
      });
    return () => { cancelled = true; };
  }, [navigate, userId]);

  function setPref(key, val) {
    setPrefs((p) => ({ ...p, [key]: val }));
  }

  function toggleDay(day) {
    setPrefs((p) => {
      const days = p.activeDays.includes(day)
        ? p.activeDays.filter((d) => d !== day)
        : [...p.activeDays, day];
      return { ...p, activeDays: days };
    });
  }

  // family/contacts/providers sync through the backend immediately --
  // these are individual rows in their own tables, batching them onto
  // Save would mean tracking adds/removes in a queue and replaying on
  // Save click. Not worth the complexity at current scale.
  async function addMember() {
    if (!newMember.name.trim()) return;
    try {
      const created = await createFamilyMember(userId, {
        name: newMember.name.trim(),
        relation: newMember.relation.trim() || null,
        phone_number: newMember.phone_number.trim() || null,
      });
      setFamilyMembers((ms) => [...ms, created]);
      setNewMember({ name: '', relation: '', phone_number: '' });
    } catch (err) {
      alert(`Couldn't add family member: ${err.message}`);
    }
  }
  async function removeMember(id) {
    try {
      await deleteFamilyMember(userId, id);
      setFamilyMembers((ms) => ms.filter((m) => m.id !== id));
    } catch (err) {
      alert(`Couldn't remove family member: ${err.message}`);
    }
  }

  async function addContact() {
    if (!newContact.name.trim()) return;
    try {
      const created = await createContact(userId, {
        name: newContact.name.trim(),
        role: newContact.role.trim() || null,
        org: newContact.org.trim() || null,
        phone: newContact.phone.trim() || null,
      });
      setContacts((cs) => [...cs, created]);
      setNewContact({ name: '', role: '', org: '', phone: '' });
    } catch (err) {
      alert(`Couldn't add contact: ${err.message}`);
    }
  }
  async function removeContact(id) {
    try {
      await deleteContact(userId, id);
      setContacts((cs) => cs.filter((c) => c.id !== id));
    } catch (err) {
      alert(`Couldn't remove contact: ${err.message}`);
    }
  }

  async function addProvider() {
    if (!newProvider.name.trim()) return;
    try {
      const created = await createProvider(userId, {
        name: newProvider.name.trim(),
        specialty: newProvider.specialty.trim() || null,
        practice: newProvider.practice.trim() || null,
      });
      setProviders((ps) => [...ps, created]);
      setNewProvider({ name: '', specialty: '', practice: '' });
    } catch (err) {
      alert(`Couldn't add provider: ${err.message}`);
    }
  }
  async function removeProvider(id) {
    try {
      await deleteProvider(userId, id);
      setProviders((ps) => ps.filter((p) => p.id !== id));
    } catch (err) {
      alert(`Couldn't remove provider: ${err.message}`);
    }
  }

  const dismissBanner = useCallback(() => {
    // banner-dismissed is a UI-only flag, not a backend field. keep it
    // in the cached user so it survives a refresh without round-tripping.
    setUser((u) => {
      const updated = { ...u, banner_dismissed: true };
      cacheUser(updated);
      return updated;
    });
  }, []);

  async function handleSave() {
    if (!user || !prefs || saving) return;
    setSaving(true);
    try {
      await updatePreferences(userId, prefsToBackend(prefs));
      // refetch so the cached user matches what the backend persisted
      const fresh = await fetchUser(userId);
      setUser(fresh);
      setPrefs(prefsFromBackend(fresh));
      cacheUser(fresh);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      alert(`Couldn't save preferences: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  if (loadError) return <div className="page-loading">Error: {loadError}</div>;
  if (!user || !prefs) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1 className="page-title">Profile & Preferences</h1>

      {user.banner_dismissed !== true && (
        <Banner
          message="G is active — text or call +1 (510) 945-3573 to get started."
          onDismiss={dismissBanner}
        />
      )}

      {/* ─── Your Info ─────────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Your Info</h2>
        <div className="info-row">
          <span className="info-label">Name</span>
          <span>{user.name || '—'}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Phone</span>
          <span>{user.phone_number || '—'}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Email</span>
          <span>{user.email || '—'}</span>
        </div>
      </section>

      {/* ─── Family Members ────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Family Members</h2>
        {familyMembers.length > 0 && (
          <ul className="member-list">
            {familyMembers.map((m) => (
              <li key={m.id} className="member-item">
                <span>
                  {m.name}{' '}
                  {m.relation && <span className="member-relation">({m.relation})</span>}
                  {m.phone_number && <span className="contact-phone"> · {m.phone_number}</span>}
                </span>
                <button className="btn-remove" onClick={() => removeMember(m.id)}>✕</button>
              </li>
            ))}
          </ul>
        )}
        <div className="add-member-row">
          <input
            className="text-input"
            placeholder="Name"
            value={newMember.name}
            onChange={(e) => setNewMember((m) => ({ ...m, name: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && addMember()}
          />
          <input
            className="text-input"
            placeholder="Relation"
            value={newMember.relation}
            onChange={(e) => setNewMember((m) => ({ ...m, relation: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && addMember()}
          />
          <input
            type="tel"
            className="text-input"
            placeholder="Phone (optional)"
            value={newMember.phone_number}
            onChange={(e) => setNewMember((m) => ({ ...m, phone_number: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && addMember()}
          />
          <button className="btn btn-primary" onClick={addMember}>Add</button>
        </div>
      </section>

      {/* ─── Contacts ──────────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Contacts</h2>
        <p className="card-description">People G may need to call — schools, doctors' offices, service providers.</p>
        {contacts.length > 0 && (
          <ul className="member-list">
            {contacts.map((c) => (
              <li key={c.id} className="member-item">
                <div>
                  <span className="contact-name">{c.name}</span>
                  {(c.role || c.org) && (
                    <span className="member-relation">
                      {' · '}{c.role}{c.org ? ` at ${c.org}` : ''}
                    </span>
                  )}
                  {c.phone && <span className="contact-phone"> · {c.phone}</span>}
                </div>
                <button className="btn-remove" onClick={() => removeContact(c.id)}>✕</button>
              </li>
            ))}
          </ul>
        )}
        <div className="add-contact-form">
          <div className="add-member-row">
            <input
              className="text-input"
              placeholder="Name"
              value={newContact.name}
              onChange={(e) => setNewContact((c) => ({ ...c, name: e.target.value }))}
            />
            <input
              className="text-input"
              placeholder="Role (e.g. Office Manager)"
              value={newContact.role}
              onChange={(e) => setNewContact((c) => ({ ...c, role: e.target.value }))}
            />
          </div>
          <div className="add-member-row" style={{ marginTop: '8px' }}>
            <input
              className="text-input"
              placeholder="Organization (optional)"
              value={newContact.org}
              onChange={(e) => setNewContact((c) => ({ ...c, org: e.target.value }))}
            />
            <input
              className="text-input"
              placeholder="Phone (optional)"
              value={newContact.phone}
              onChange={(e) => setNewContact((c) => ({ ...c, phone: e.target.value }))}
            />
            <button className="btn btn-primary" onClick={addContact}>Add</button>
          </div>
        </div>
      </section>

      {/* ─── Preferred Providers ───────────────────────── */}
      <section className="card">
        <h2 className="card-title">Preferred Providers</h2>
        <p className="card-description">G uses these when booking appointments or making referrals.</p>
        {providers.length > 0 && (
          <ul className="member-list">
            {providers.map((p) => (
              <li key={p.id} className="member-item">
                <div>
                  <span className="contact-name">{p.name}</span>
                  <span className="member-relation">
                    {' · '}{p.specialty}{p.practice ? ` at ${p.practice}` : ''}
                  </span>
                </div>
                <button className="btn-remove" onClick={() => removeProvider(p.id)}>✕</button>
              </li>
            ))}
          </ul>
        )}
        <div className="add-member-row">
          <input
            className="text-input"
            placeholder="Name"
            value={newProvider.name}
            onChange={(e) => setNewProvider((p) => ({ ...p, name: e.target.value }))}
          />
          <input
            className="text-input"
            placeholder="Specialty"
            value={newProvider.specialty}
            onChange={(e) => setNewProvider((p) => ({ ...p, specialty: e.target.value }))}
          />
          <input
            className="text-input"
            placeholder="Practice (optional)"
            value={newProvider.practice}
            onChange={(e) => setNewProvider((p) => ({ ...p, practice: e.target.value }))}
          />
          <button className="btn btn-primary" onClick={addProvider}>Add</button>
        </div>
      </section>

      {/* ─── Communication ─────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Communication</h2>

        <div className="pref-row">
          <span className="pref-label">Communication style</span>
          <div className="pref-choice">
            <button
              className={`choice-btn ${prefs.communicationStyle === 'brief' ? 'active' : ''}`}
              onClick={() => setPref('communicationStyle', 'brief')}
            >
              Brief
            </button>
            <button
              className={`choice-btn ${prefs.communicationStyle === 'detailed' ? 'active' : ''}`}
              onClick={() => setPref('communicationStyle', 'detailed')}
            >
              Detailed
            </button>
          </div>
        </div>

        <div className="pref-row">
          <span className="pref-label">Preferred contact method</span>
          <div className="pref-choice">
            <button
              className={`choice-btn ${prefs.preferredContact === 'text' ? 'active' : ''}`}
              onClick={() => setPref('preferredContact', 'text')}
            >
              Text
            </button>
            <button
              className={`choice-btn ${prefs.preferredContact === 'call' ? 'active' : ''}`}
              onClick={() => setPref('preferredContact', 'call')}
            >
              Call
            </button>
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Call instead of text when urgency is</span>
          <div className="pill-options">
            <button
              className={`pill-btn ${prefs.callUrgencyThreshold === 'any' ? 'active' : ''}`}
              onClick={() => setPref('callUrgencyThreshold', 'any')}
            >
              Any urgency
            </button>
            <button
              className={`pill-btn ${prefs.callUrgencyThreshold === 'high' ? 'active' : ''}`}
              onClick={() => setPref('callUrgencyThreshold', 'high')}
            >
              High only
            </button>
            <button
              className={`pill-btn ${prefs.callUrgencyThreshold === 'never' ? 'active' : ''}`}
              onClick={() => setPref('callUrgencyThreshold', 'never')}
            >
              Never call
            </button>
          </div>
        </div>
      </section>

      {/* ─── Notification Timing ───────────────────────── */}
      <section className="card">
        <h2 className="card-title">Notification Timing</h2>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Quiet hours — G won't contact you during this window</span>
          <div className="time-range">
            <TimePicker
              label="From"
              value={prefs.quietHoursStart}
              onChange={(v) => setPref('quietHoursStart', v)}
            />
            <TimePicker
              label="To"
              value={prefs.quietHoursEnd}
              onChange={(v) => setPref('quietHoursEnd', v)}
            />
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Keep-free window — G won't schedule tasks during this time</span>
          <div className="time-range">
            <TimePicker
              label="From"
              value={prefs.keepFreeStart}
              onChange={(v) => setPref('keepFreeStart', v)}
            />
            <TimePicker
              label="To"
              value={prefs.keepFreeEnd}
              onChange={(v) => setPref('keepFreeEnd', v)}
            />
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Days G is active</span>
          <div className="day-picker">
            {DAYS.map((day) => (
              <button
                key={day.key}
                className={`day-btn ${prefs.activeDays.includes(day.key) ? 'active' : ''}`}
                onClick={() => toggleDay(day.key)}
              >
                {day.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Morning Digest ─────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Morning Digest</h2>

        <Toggle
          label="Send morning digest"
          checked={prefs.morningDigest}
          onChange={(v) => setPref('morningDigest', v)}
        />

        {prefs.morningDigest && (
          <>
            <div className="pref-row">
              <span className="pref-label">Digest time</span>
              <TimePicker
                label=""
                value={prefs.digestTime}
                onChange={(v) => setPref('digestTime', v)}
              />
            </div>

            <div className="pref-row pref-row--block">
              <span className="pref-label">Include in digest</span>
              <div className="pill-options">
                <button
                  className={`pill-btn ${prefs.digestContent === 'calendar' ? 'active' : ''}`}
                  onClick={() => setPref('digestContent', 'calendar')}
                >
                  Calendar only
                </button>
                <button
                  className={`pill-btn ${prefs.digestContent === 'calendar+email' ? 'active' : ''}`}
                  onClick={() => setPref('digestContent', 'calendar+email')}
                >
                  + Unread emails
                </button>
                <button
                  className={`pill-btn ${prefs.digestContent === 'calendar+tasks' ? 'active' : ''}`}
                  onClick={() => setPref('digestContent', 'calendar+tasks')}
                >
                  + Pending tasks
                </button>
              </div>
            </div>

            <Toggle
              label="Include travel time estimates between events"
              checked={prefs.digestTravelTime}
              onChange={(v) => setPref('digestTravelTime', v)}
            />
          </>
        )}
      </section>

      {/* ─── Escalation Behavior ───────────────────────── */}
      <section className="card">
        <h2 className="card-title">Escalation Behavior</h2>

        <div className="pref-row">
          <span className="pref-label">Escalation timeout</span>
          <div className="number-stepper">
            <button
              onClick={() =>
                setPref('escalationTimeoutMinutes', Math.max(5, prefs.escalationTimeoutMinutes - 5))
              }
            >
              −
            </button>
            <span className="stepper-value">{prefs.escalationTimeoutMinutes} min</span>
            <button
              onClick={() =>
                setPref('escalationTimeoutMinutes', Math.min(120, prefs.escalationTimeoutMinutes + 5))
              }
            >
              +
            </button>
          </div>
        </div>

        <Toggle
          label="Auto-approve low-risk actions (e.g. adding calendar events — deletions still require approval)"
          checked={prefs.autoApproveLowRisk}
          onChange={(v) => setPref('autoApproveLowRisk', v)}
        />

        <div className="pref-row">
          <span className="pref-label">Reminders before giving up on a response</span>
          <div className="number-stepper">
            <button
              onClick={() => setPref('maxReminders', Math.max(1, prefs.maxReminders - 1))}
            >
              −
            </button>
            <span className="stepper-value">{prefs.maxReminders}</span>
            <button
              onClick={() => setPref('maxReminders', Math.min(10, prefs.maxReminders + 1))}
            >
              +
            </button>
          </div>
        </div>
      </section>

      {/* ─── G's Behavior ──────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">G's Behavior</h2>

        <div className="pref-row">
          <span className="pref-label">Tone</span>
          <div className="pref-choice">
            <button
              className={`choice-btn ${prefs.tone === 'casual' ? 'active' : ''}`}
              onClick={() => setPref('tone', 'casual')}
            >
              Casual
            </button>
            <button
              className={`choice-btn ${prefs.tone === 'formal' ? 'active' : ''}`}
              onClick={() => setPref('tone', 'formal')}
            >
              Formal
            </button>
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">Send reminders how far ahead</span>
          <div className="pill-options">
            <button
              className={`pill-btn ${prefs.reminderLeadTime === '15' ? 'active' : ''}`}
              onClick={() => setPref('reminderLeadTime', '15')}
            >
              15 min
            </button>
            <button
              className={`pill-btn ${prefs.reminderLeadTime === '30' ? 'active' : ''}`}
              onClick={() => setPref('reminderLeadTime', '30')}
            >
              30 min
            </button>
            <button
              className={`pill-btn ${prefs.reminderLeadTime === '60' ? 'active' : ''}`}
              onClick={() => setPref('reminderLeadTime', '60')}
            >
              1 hour
            </button>
            <button
              className={`pill-btn ${prefs.reminderLeadTime === '1440' ? 'active' : ''}`}
              onClick={() => setPref('reminderLeadTime', '1440')}
            >
              Day before
            </button>
          </div>
        </div>

        <div className="pref-row pref-row--block">
          <span className="pref-label">When G spots a scheduling conflict</span>
          <div className="pref-choice">
            <button
              className={`choice-btn ${prefs.conflictHandling === 'suggest' ? 'active' : ''}`}
              onClick={() => setPref('conflictHandling', 'suggest')}
            >
              Suggest reschedule
            </button>
            <button
              className={`choice-btn ${prefs.conflictHandling === 'flag' ? 'active' : ''}`}
              onClick={() => setPref('conflictHandling', 'flag')}
            >
              Just flag it
            </button>
          </div>
        </div>
      </section>

      <div className="save-row">
        <button className="btn btn-primary btn-save" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save changes'}
        </button>
      </div>
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: chose immediate-sync for family/contact/provider
// add+remove instead of a queue-then-batch-on-save model. Backend rows
// each have their own id and the user expects the list to reflect what
// they just did -- queuing means the UI lies until they hit Save. The
// downside is each add/remove costs one round-trip; at the row counts
// we care about (single digits) that's fine. Save is reserved for the
// preference dial that has no per-row identity. updateProfile (PATCH
// for name/email) is intentionally not wired here since the page doesn't
// expose name/email as editable fields; if that ships later, fold it
// into handleSave next to updatePreferences.
