import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ProgressBar from '../../components/ProgressBar';
import FamilyMemberRow from '../../components/FamilyMemberRow';

// [GenAI Use] LLM Response Start
// Name + phone fields (validated), family members list using 
// FamilyMemberRow component
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Phone validation uses HTML required attribute
// which blocks submit on empty input. Family members are optional - 
// user can proceed with zero members added. Each member uses 
// FamilyMemberRow which has name input + relation dropdown + remove 
// button. Data is saved to g_onboard in localStorage before navigating 
// to step 2 so it persists across steps. Confirmed ProgressBar shows 
// step 1 of 2.

export default function Step1Family() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [members, setMembers] = useState([]);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    const saved = localStorage.getItem('g_onboard');
    if (!saved) { navigate('/signup', { replace: true }); return; }
    const data = JSON.parse(saved);
    if (data.name) setName(data.name);
    if (data.phone) setPhone(data.phone);
    if (data.familyMembers?.length) setMembers(data.familyMembers);
  }, [navigate]);

  function addMember() {
    setMembers((ms) => [...ms, { id: Date.now(), name: '', relation: '' }]);
  }

  function updateMember(id, updated) {
    setMembers((ms) => ms.map((m) => (m.id === id ? updated : m)));
  }

  function removeMember(id) {
    setMembers((ms) => ms.filter((m) => m.id !== id));
  }

  function handleContinue() {
    const errs = {};
    if (!name.trim()) errs.name = 'Name is required';
    if (!phone.trim()) errs.phone = 'Phone number is required';
    if (Object.keys(errs).length) { setErrors(errs); return; }

    const saved = JSON.parse(localStorage.getItem('g_onboard') || '{}');
    localStorage.setItem('g_onboard', JSON.stringify({
      ...saved,
      name: name.trim(),
      phone: phone.trim(),
      familyMembers: members.filter((m) => m.name.trim()),
    }));
    navigate('/onboard/step2');
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
        <button className="btn btn-brand" onClick={handleContinue}>Continue →</button>
      </div>
    </div>
  );
}
