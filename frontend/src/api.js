import { getToken } from './auth';

const API_BASE = '';

function authHeaders(extra = {}) {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options.headers),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function register(name, email, password) {
  return apiFetch('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ name, email, password }),
  });
}

export async function login(email, password) {
  return apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

// re-fetch the backend's view of a user. used after onboarding writes to
// pull the canonical state into localStorage instead of mutating
// fields ad-hoc and risking drift.
export async function fetchUser(userId) {
  return apiFetch(`/api/users/${userId}`);
}

// PATCH name/email/phone_number. phone_number is settable only when the
// user's current phone is null (first-time onboarding); the backend rejects
// a swap on an already-set phone.
export async function updateProfile(userId, patch) {
  return apiFetch(`/api/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

// PATCH preferences. `patch` must use the backend's snake_case keys --
// see UserPreferencesUpdate in backend/schemas/user.py. Step2Preferences
// maps the form state into this shape before calling.
export async function updatePreferences(userId, patch) {
  return apiFetch(`/api/users/${userId}/preferences`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

// POST one family member. Step1Family loops over the user's added rows
// and calls this per row -- the backend doesn't currently expose a bulk
// endpoint and the row count in practice is single digits.
export async function createFamilyMember(userId, member) {
  return apiFetch(`/api/users/${userId}/family-members`, {
    method: 'POST',
    body: JSON.stringify(member),
  });
}

export async function listFamilyMembers(userId) {
  return apiFetch(`/api/users/${userId}/family-members`);
}

export async function deleteFamilyMember(userId, memberId) {
  return apiFetch(`/api/users/${userId}/family-members/${memberId}`, {
    method: 'DELETE',
  });
}

// contacts: third parties G might call/text on the user's behalf.
export async function listContacts(userId) {
  return apiFetch(`/api/users/${userId}/contacts`);
}

export async function createContact(userId, contact) {
  return apiFetch(`/api/users/${userId}/contacts`, {
    method: 'POST',
    body: JSON.stringify(contact),
  });
}

export async function deleteContact(userId, contactId) {
  return apiFetch(`/api/users/${userId}/contacts/${contactId}`, {
    method: 'DELETE',
  });
}

// providers: doctors / lawyers / preferred service providers.
export async function listProviders(userId) {
  return apiFetch(`/api/users/${userId}/providers`);
}

export async function createProvider(userId, provider) {
  return apiFetch(`/api/users/${userId}/providers`, {
    method: 'POST',
    body: JSON.stringify(provider),
  });
}

export async function deleteProvider(userId, providerId) {
  return apiFetch(`/api/users/${userId}/providers/${providerId}`, {
    method: 'DELETE',
  });
}

// All API calls go here. Mocked for now — replace individual functions with real fetch calls when backend is ready.
// [GenAI Use] LLM Response Start
// Added sendMessage() which calls Anthropic API or falls back to
// keyword-matched mock. Added parseTaskBlock() to extract task data
// from task XML tags in AI responses.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: parseTaskBlock() looks for task tags in
// the response text and pulls out the task fields. Verified it handles
// responses with no task block correctly by returning null. The mock
// returns task blocks for keywords like reminder, schedule, escalation
// so the UI can be tested without a real API key.
// Consulted: https://docs.anthropic.com/en/api/messages

const MOCK_RESPONSES = [
  { keywords: ['remind', 'reminder'], reply: "Got it! I'll set a reminder for you.", task: { type: 'Reminder', status: 'Pending', description: null, summary: '' } },
  { keywords: ['schedule', 'calendar', 'appointment', 'meeting'], reply: "I'll add that to your calendar.", task: { type: 'Calendar', status: 'Pending', description: null, summary: '' } },
  { keywords: ['call', 'escalat', 'contact', 'reach'], reply: "I'll handle that for you and report back.", task: { type: 'Escalation', status: 'In Progress', description: null, summary: '' } },
];

export async function sendMessage(messages, userId = null) {
  const lastUser = messages[messages.length - 1]?.content ?? '';
  try {
    const data = await apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message: lastUser, user_id: userId }),
    });
    return data.reply;
  } catch (err) {
    // Mock fallback if backend is unreachable
    const lower = lastUser.toLowerCase();
    const match = MOCK_RESPONSES.find((m) => m.keywords.some((k) => lower.includes(k)));
    if (match) {
      const desc = lastUser.slice(0, 60);
      return `${match.reply}\n<task><type>${match.task.type}</type><status>${match.task.status}</status><description>${desc}</description><summary>${match.task.summary}</summary></task>`;
    }
    return "I'm here to help! You can ask me to set reminders, schedule events, or handle tasks on your behalf.";
  }
}

export function parseTaskBlock(raw) {
  const match = raw.match(/<task>([\s\S]*?)<\/task>/);
  if (!match) return { cleanText: raw.trim(), task: null };

  const xml = match[1];
  const get = (tag) => xml.match(new RegExp(`<${tag}>(.*?)</${tag}>`))?.[1]?.trim() ?? '';

  return {
    cleanText: raw.replace(/<task>[\s\S]*?<\/task>/, '').trim(),
    task: {
      type: get('type') || 'Reminder',
      status: get('status') || 'Pending',
      description: get('description'),
      summary: get('summary'),
    },
  };
}

export async function getUser() {
  return {
    name: 'Alex Johnson',
    phone: '+1 (310) 555-0182',
    email: 'alex.johnson@example.com',
    familyMembers: [
      { id: 1, name: 'Sarah Johnson', relation: 'Spouse' },
      { id: 2, name: 'Mark Johnson', relation: 'Son' },
      { id: 3, name: 'Emma Johnson', relation: 'Daughter' },
    ],
    contacts: [
      { id: 1, name: 'Mrs. Carter', role: 'Office Manager', org: "Mark's School", phone: '(310) 555-0201' },
      { id: 2, name: "Dr. Kim's Office", role: 'Pediatrician', org: 'Cedar Medical', phone: '(310) 555-0344' },
    ],
    providers: [
      { id: 1, name: 'Dr. Lee', specialty: 'Dentist', practice: 'UCLA Westside Dental' },
      { id: 2, name: 'Dr. Kim', specialty: 'Pediatrician', practice: 'Cedar Medical Group' },
      { id: 3, name: 'Westside Plumbing', specialty: 'Plumber', practice: '' },
    ],
    preferences: {
      // Communication
      communicationStyle: 'brief',
      preferredContact: 'text',
      callUrgencyThreshold: 'high', // 'any' | 'high' | 'never'
      // Notification timing
      quietHoursStart: '22:00',
      quietHoursEnd: '07:00',
      keepFreeStart: '22:00',
      keepFreeEnd: '07:00',
      activeDays: ['mon', 'tue', 'wed', 'thu', 'fri'],
      // Morning digest
      morningDigest: true,
      digestTime: '08:00',
      digestContent: 'calendar+tasks', // 'calendar' | 'calendar+email' | 'calendar+tasks'
      digestTravelTime: false,
      // Escalation
      escalationTimeoutMinutes: 30,
      autoApproveLowRisk: true,
      maxReminders: 3,
      // G's behavior
      tone: 'casual', // 'casual' | 'formal'
      reminderLeadTime: '60', // minutes: '15' | '30' | '60' | '1440'
      conflictHandling: 'suggest', // 'suggest' | 'flag'
    },
  };
}

export async function saveUser(data) {
  console.log('POST /api/users/me', data);
}

// kept for any callers still pointing at the old mock task-history view --
// not used by the live Conversations page anymore (see getMessages below).
export async function getTaskHistory() {
  return MOCK_TASK_HISTORY;
}

// real backend fetch -- TaskResponse rows newest first.
// shape: { id, status, type, description, plan_steps, escalation_deadline,
//          created_at, updated_at }
export async function getTasks(userId, limit = 50) {
  return apiFetch(`/api/users/${userId}/tasks?limit=${limit}`);
}

// real backend fetch for the History page -- message audit log newest first.
// shape: { id, content, direction, channel, timestamp, task_id, user_id }
export async function getMessages(userId, limit = 200) {
  return apiFetch(`/api/users/${userId}/messages?limit=${limit}`);
}

export async function approveEscalation(taskId) {
  return apiFetch(`/api/tasks/${taskId}/approve`, { method: 'POST' });
}

export async function denyEscalation(taskId) {
  return apiFetch(`/api/tasks/${taskId}/deny`, { method: 'POST' });
}

const MOCK_TASK_HISTORY = [
  {
    id: 'th-001',
    description: 'Remind me to pick up Mark at 4pm today',
    type: 'Reminder',
    status: 'COMPLETED',
    createdAt: '2026-05-24T15:02:00Z',
    completedAt: '2026-05-24T15:55:30Z',
    channel: 'sms',
    conversation: [
      {
        id: 1,
        direction: 'inbound',
        channel: 'sms',
        content: 'Remind me to pick up Mark at 4pm today',
        timestamp: '2026-05-24T15:02:00Z',
        taskCreated: false,
      },
      {
        id: 2,
        direction: 'outbound',
        channel: 'sms',
        content: "Got it! I'll remind you to pick up Mark at 4:00 PM today.",
        timestamp: '2026-05-24T15:02:18Z',
        taskCreated: true,
      },
      {
        id: 3,
        direction: 'outbound',
        channel: 'sms',
        content: "Heads up — it's almost 4 PM! Time to pick up Mark.",
        timestamp: '2026-05-24T15:55:00Z',
        taskCreated: false,
      },
      {
        id: 4,
        direction: 'inbound',
        channel: 'sms',
        content: 'Thanks, on my way!',
        timestamp: '2026-05-24T15:56:10Z',
        taskCreated: false,
      },
    ],
  },
  {
    id: 'th-002',
    description: "Schedule a dentist appointment for Emma next week after 3pm",
    type: 'Calendar',
    status: 'COMPLETED',
    createdAt: '2026-05-24T15:03:45Z',
    completedAt: '2026-05-24T16:15:00Z',
    channel: 'sms',
    conversation: [
      {
        id: 1,
        direction: 'inbound',
        channel: 'sms',
        content: "Can you schedule a dentist appointment for Emma sometime next week? She's free after 3pm",
        timestamp: '2026-05-24T15:03:45Z',
        taskCreated: false,
      },
      {
        id: 2,
        direction: 'outbound',
        channel: 'sms',
        content: "On it! I'll check availability at Westside Dental and let you know.",
        timestamp: '2026-05-24T15:03:58Z',
        taskCreated: true,
      },
      {
        id: 3,
        direction: 'outbound',
        channel: 'sms',
        content: "I found an opening at Westside Dental on Tuesday May 28 at 3:30 PM. Should I confirm?",
        timestamp: '2026-05-24T16:10:00Z',
        taskCreated: false,
      },
      {
        id: 4,
        direction: 'inbound',
        channel: 'sms',
        content: 'Yes go ahead and book it',
        timestamp: '2026-05-24T16:12:30Z',
        taskCreated: false,
      },
      {
        id: 5,
        direction: 'outbound',
        channel: 'sms',
        content: "Done! Appointment confirmed: Emma Johnson, Westside Dental, Tuesday May 28 at 3:30 PM. Added to your calendar.",
        timestamp: '2026-05-24T16:14:55Z',
        taskCreated: false,
      },
    ],
  },
  {
    id: 'th-003',
    description: 'Call the insurance company about the claim from last month',
    type: 'Escalation',
    status: 'COMPLETED',
    createdAt: '2026-05-23T09:15:00Z',
    completedAt: '2026-05-23T09:58:00Z',
    channel: 'voice',
    callDuration: '3m 42s',
    transcript: [
      { speaker: 'User', text: "I need you to call the insurance company about a claim I submitted last month. The claim number is 8847-B.", time: '0:00' },
      { speaker: 'G', text: "Got it. Which insurance company, and do you have their number handy?", time: '0:08' },
      { speaker: 'User', text: "BlueCross. 1-800-555-0134.", time: '0:15' },
      { speaker: 'G', text: "I'll call them now and check on claim 8847-B. I'll report back once I have an update.", time: '0:22' },
      { speaker: 'G', text: "Reached BlueCross. Claim 8847-B is under review — expect a decision within 5 business days. Reference: CR-2291.", time: '0:38' },
      { speaker: 'User', text: "Great, thanks.", time: '0:44' },
    ],
  },
  {
    id: 'th-004',
    description: "Order more of Sarah's blood pressure medication from the pharmacy",
    type: 'Reminder',
    status: 'FAILED',
    createdAt: '2026-05-23T11:30:00Z',
    completedAt: '2026-05-23T12:15:00Z',
    channel: 'sms',
    conversation: [
      {
        id: 1,
        direction: 'inbound',
        channel: 'sms',
        content: "Can you order more of Sarah's blood pressure medication from CVS? Prescription RX-4492.",
        timestamp: '2026-05-23T11:30:00Z',
        taskCreated: false,
      },
      {
        id: 2,
        direction: 'outbound',
        channel: 'sms',
        content: "Sure, I'll contact CVS about refilling prescription RX-4492 for Sarah. Give me a moment.",
        timestamp: '2026-05-23T11:30:22Z',
        taskCreated: true,
      },
      {
        id: 3,
        direction: 'outbound',
        channel: 'sms',
        content: "CVS says this prescription requires prescriber authorization before it can be refilled. You'll need to contact Dr. Kim's office to request a new authorization.",
        timestamp: '2026-05-23T12:14:40Z',
        taskCreated: false,
      },
    ],
  },
  {
    id: 'th-005',
    description: 'Set up a playdate for Mark with Tyler next Saturday afternoon',
    type: 'Calendar',
    status: 'COMPLETED',
    createdAt: '2026-05-22T18:00:00Z',
    completedAt: '2026-05-22T18:22:00Z',
    channel: 'voice',
    callDuration: '1m 58s',
    transcript: [
      { speaker: 'User', text: "Can you help me set up a playdate for Mark with his friend Tyler next Saturday afternoon?", time: '0:00' },
      { speaker: 'G', text: "Happy to help. Do you have Tyler's parents' contact info, or should I look them up from your contacts?", time: '0:09' },
      { speaker: 'User', text: "They're in my contacts — Taylor family.", time: '0:18' },
      { speaker: 'G', text: "Found them. Would you prefer a text or a call to coordinate?", time: '0:24' },
      { speaker: 'User', text: "Text is fine, just check if Saturday afternoon works for them.", time: '0:30' },
      { speaker: 'G', text: "Done — texted the Taylors. I'll let you know once they respond and block tentative time Saturday 1–4 PM for now.", time: '0:38' },
    ],
  },
];

const MOCK_TASKS = [
  {
    id: 'task-001',
    description: 'Remind me to pick up Mark at 4pm today',
    type: 'Reminder',
    status: 'COMPLETED',
    createdAt: '2026-05-24T15:02:00Z',
    summary: "Sent reminder at 3:55 PM: \"Heads up — it's almost 4 PM! Time to pick up Mark.\"",
  },
  {
    id: 'task-002',
    description: "Schedule a dentist appointment for Emma next week after 3pm",
    type: 'Calendar',
    status: 'ESCALATION_PENDING',
    createdAt: '2026-05-24T15:03:45Z',
    escalationQuestion: "I found an opening at Westside Dental on Tuesday May 28 at 3:30 PM. Should I confirm this appointment?",
    escalationCreatedAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
  },
  {
    id: 'task-003',
    description: 'Call the insurance company about the claim from last month',
    type: 'Escalation',
    status: 'IN_PROGRESS',
    createdAt: '2026-05-24T09:15:00Z',
  },
  {
    id: 'task-004',
    description: "Order more of Sarah's blood pressure medication from the pharmacy",
    type: 'Reminder',
    status: 'PENDING',
    createdAt: '2026-05-24T11:30:00Z',
  },
  {
    id: 'task-005',
    description: 'Find a plumber to fix the leak under the kitchen sink',
    type: 'Escalation',
    status: 'FAILED',
    createdAt: '2026-05-23T14:00:00Z',
    summary: 'Unable to reach any available plumbers in the area. Please try calling directly.',
  },
];
