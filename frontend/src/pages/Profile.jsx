import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getUser as loadUser, setUser as persistUser, isLoggedIn } from '../auth';
import Toggle from '../components/Toggle';
import TimePicker from '../components/TimePicker';
import Banner from '../components/Banner';
// [GenAI Use] LLM Response Start
// Reads from localStorage via getUser(), redirects to /signup if not 
// logged in, shows dismissable banner on first post-onboarding visit,
// Save logs and persists to localStorage
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: The redirect to /signup when isLoggedIn() 
// returns false is a basic auth guard - prevents unauthenticated access.
// Will need to be replaced with a real auth check when backend sessions 
// are implemented. Save currently only persists to localStorage, not 
// the backend - noted as a gap to address when PATCH /api/users/{id}/
// preferences is fully connected.

const DAYS = [
  { key: 'mon', label: 'M' },
  { key: 'tue', label: 'Tu' },
  { key: 'wed', label: 'W' },
  { key: 'thu', label: 'Th' },
  { key: 'fri', label: 'F' },
  { key: 'sat', label: 'Sa' },
  { key: 'sun', label: 'Su' },
];

export default function Profile() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [prefs, setPrefs] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newMember, setNewMember] = useState({ name: '', relation: '', phone_number: '' });
  const [newContact, setNewContact] = useState({ name: '', role: '', org: '', phone: '' });
  const [newProvider, setNewProvider] = useState({ name: '', specialty: '', practice: '' });

  useEffect(() => {
    if (!isLoggedIn()) { navigate('/signup', { replace: true }); return; }
    const u = loadUser();
    setUser(u);
    setPrefs({ ...u.preferences });
  }, [navigate]);

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

  function addMember() {
    if (!newMember.name.trim()) return;
    setUser((u) => ({ ...u, familyMembers: [...u.familyMembers, { id: Date.now(), ...newMember }] }));
    setNewMember({ name: '', relation: '', phone_number: '' });
  }
  function removeMember(id) {
    setUser((u) => ({ ...u, familyMembers: u.familyMembers.filter((m) => m.id !== id) }));
  }

  function addContact() {
    if (!newContact.name.trim()) return;
    setUser((u) => ({ ...u, contacts: [...(u.contacts || []), { id: Date.now(), ...newContact }] }));
    setNewContact({ name: '', role: '', org: '', phone: '' });
  }
  function removeContact(id) {
    setUser((u) => ({ ...u, contacts: u.contacts.filter((c) => c.id !== id) }));
  }

  function addProvider() {
    if (!newProvider.name.trim()) return;
    setUser((u) => ({ ...u, providers: [...(u.providers || []), { id: Date.now(), ...newProvider }] }));
    setNewProvider({ name: '', specialty: '', practice: '' });
  }
  function removeProvider(id) {
    setUser((u) => ({ ...u, providers: u.providers.filter((p) => p.id !== id) }));
  }

  function dismissBanner() {
    const updated = { ...user, bannerDismissed: true };
    setUser(updated);
    persistUser(updated);
  }

  async function handleSave() {
    setSaving(true);
    const updated = { ...user, preferences: prefs };
    console.log('Save payload:', updated);
    persistUser(updated);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  if (!user || !prefs) return <div className="page-loading">Loading…</div>;

  return (
    <div className="page">
      <h1 className="page-title">Profile & Preferences</h1>

      {user.bannerDismissed === false && (
        <Banner
          message="G is active — save this number: (555) 010-GAAI"
          onDismiss={dismissBanner}
        />
      )}

      {/* ─── Your Info ─────────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Your Info</h2>
        <div className="info-row">
          <span className="info-label">Name</span>
          <span>{user.name}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Phone</span>
          <span>{user.phone}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Email</span>
          <span>{user.email}</span>
        </div>
      </section>

      {/* ─── Family Members ────────────────────────────── */}
      <section className="card">
        <h2 className="card-title">Family Members</h2>
        {user.familyMembers.length > 0 && (
          <ul className="member-list">
            {user.familyMembers.map((m) => (
              <li key={m.id} className="member-item">
                <span>
                  {m.name} <span className="member-relation">({m.relation})</span>
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
        {(user.contacts || []).length > 0 && (
          <ul className="member-list">
            {user.contacts.map((c) => (
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
        {(user.providers || []).length > 0 && (
          <ul className="member-list">
            {user.providers.map((p) => (
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
