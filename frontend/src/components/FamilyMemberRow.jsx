const RELATIONS = ['Child', 'Spouse', 'Parent', 'Sibling', 'Other'];

// [GenAI Use] LLM Response Start
// Name input + relation dropdown (Child/Spouse/Parent/Sibling/Other) 
// + remove button
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Relation options (Child/Spouse/Parent/
// Sibling/Other) match the schema defined in the backend user model.
// Remove button calls a callback passed from Step1Family to filter 
// the member out of the array. Verified controlled inputs update 
// parent state correctly via onChange handlers.

export default function FamilyMemberRow({ member, onChange, onRemove }) {
  return (
    <div className="family-member-row">
      <input
        className="text-input"
        placeholder="Name"
        value={member.name}
        onChange={(e) => onChange({ ...member, name: e.target.value })}
      />
      <select
        className="select-input"
        value={member.relation}
        onChange={(e) => onChange({ ...member, relation: e.target.value })}
      >
        <option value="">Relation</option>
        {RELATIONS.map((r) => (
          <option key={r} value={r}>{r}</option>
        ))}
      </select>
      <input
        type="tel"
        className="text-input"
        placeholder="Phone (optional)"
        value={member.phone_number}
        onChange={(e) => onChange({ ...member, phone_number: e.target.value })}
      />
      <button className="btn-remove" onClick={onRemove} aria-label="Remove">✕</button>
    </div>
  );
}
