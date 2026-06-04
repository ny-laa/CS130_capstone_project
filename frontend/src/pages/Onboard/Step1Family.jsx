import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { isLoggedIn, getUser, setUser } from '../../auth';
import { updateProfile, createFamilyMember, fetchUser } from '../../api';
import ProgressBar from '../../components/ProgressBar';
import FamilyMemberRow from '../../components/FamilyMemberRow';

// [GenAI Use] Prompt: "Step1Family used to gate on a localStorage key
// (g_onboard) that the new password-signup flow doesn't set, so users
// bounced back to /signup -> /tasks and skipped onboarding entirely.
// Drop the g_onboard guard; the backend user from signup is already in
// localStorage as g_user. On Continue, PATCH /api/users/{id} with the
// phone (first-time set) and any name change, then POST each family
// member to /api/users/{id}/family-members. Refresh the local g_user
// from the backend before navigating to step 2 so subsequent screens
// see the canonical state."
// [GenAI Use] LLM Response Start

export default function Step1Family() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [members, setMembers] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    if (!isLoggedIn()) {
      navigate('/signin?next=/onboard/step1', { replace: true });
      return;
    }
    // hydrate name from the backend user we got at signup; phone is blank
    // because register() doesn't take a phone yet -- user fills it here.
    const u = getUser();
    if (u?.name) setName(u.name);
    if (u?.phone_number) setPhone(u.phone_number);
  }, [navigate]);

  function addMember() {
    setMembers((ms) => [
      ...ms,
      { id: Date.now(), name: '', relation: '', phone_number: '' },
    ]);
  }

  function updateMember(id, updated) {
    setMembers((ms) => ms.map((m) => (m.id === id ? updated : m)));
  }

  function removeMember(id) {
    setMembers((ms) => ms.filter((m) => m.id !== id));
  }

  async function handleContinue() {
    if (submitting) return;
    const errs = {};
    if (!name.trim()) errs.name = 'Name is required';
    if (!phone.trim()) errs.phone = 'Phone number is required';
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setErrors({});
    setSubmitError('');
    setSubmitting(true);
    try {
      const user = getUser();
      if (!user?.id) throw new Error('Session expired -- please sign in again.');

      // 1. update profile (name + phone). backend ignores no-op fields.
      const profilePatch = {};
      if (name.trim() !== user.name) profilePatch.name = name.trim();
      if (phone.trim() && phone.trim() !== user.phone_number) {
        profilePatch.phone_number = phone.trim();
      }
      if (Object.keys(profilePatch).length > 0) {
        await updateProfile(user.id, profilePatch);
      }

      // 2. POST each family member with a non-empty name. one at a time
      // since the row count is tiny and per-row errors are easier to
      // surface than a bulk failure.
      const valid = members.filter((m) => m.name.trim());
      for (const m of valid) {
        await createFamilyMember(user.id, {
          name: m.name.trim(),
          relation: m.relation.trim() || null,
          phone_number: m.phone_number.trim() || null,
        });
      }

      // 3. pull canonical user state back into localStorage so step 2
      // (and Profile, eventually) reads the updated record.
      const refreshed = await fetchUser(user.id);
      setUser(refreshed);

      navigate('/onboard/step2');
    } catch (err) {
      setSubmitError(err.message || 'Could not save profile. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="onboard-page">
      <ProgressBar current={1} total={2} />
      <h1 className="onboard-title">Set up your family</h1>

      <section className="card">
        <h2 className="card-title">Your Info</h2>
        <div className="field-group">
          <label className="field-label">Your Name *</label>
          <input
            className={`text-input${errors.name ? ' input-error' : ''}`}
            placeholder="Full name"
            value={name}
            onChange={(e) => { setName(e.target.value); setErrors((p) => ({ ...p, name: '' })); }}
          />
          {errors.name && <span className="error-msg">{errors.name}</span>}
        </div>
        <div className="field-group" style={{ marginTop: 12 }}>
          <label className="field-label">Phone Number *</label>
          <input
            className={`text-input${errors.phone ? ' input-error' : ''}`}
            placeholder="+1 555 000 0000"
            value={phone}
            onChange={(e) => { setPhone(e.target.value); setErrors((p) => ({ ...p, phone: '' })); }}
          />
          {errors.phone && <span className="error-msg">{errors.phone}</span>}
        </div>
      </section>

      <section className="card">
        <h2 className="card-title">Family Members</h2>
        <p className="card-description">G can coordinate tasks and reminders across your household.</p>
        {members.map((m) => (
          <FamilyMemberRow
            key={m.id}
            member={m}
            onChange={(updated) => updateMember(m.id, updated)}
            onRemove={() => removeMember(m.id)}
          />
        ))}
        <button className="btn-add-member" onClick={addMember}>+ Add family member</button>
      </section>

      <div className="onboard-footer">
        {submitError && <span className="error-msg">{submitError}</span>}
        <button
          className="btn btn-brand"
          onClick={handleContinue}
          disabled={submitting}
        >
          {submitting ? 'Saving…' : 'Continue →'}
        </button>
      </div>
    </div>
  );
}
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: kept the per-row POST loop sequential rather
// than Promise.all because if one row fails with a 422 (e.g. a missing
// name) we want everything before it persisted, not an indeterminate
// in-flight state. The user has to retry the same screen anyway and the
// duplicate-name check is the backend's problem, not ours. Decided not
// to roll back successfully-created members on a later failure -- the
// Profile page (when wired) will let the user remove any duds.
