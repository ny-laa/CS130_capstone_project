const USER_KEY = 'g_user';
const TOKEN_KEY = 'g_token';
const PROFILES_KEY = 'g_profiles';

export function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  if (user?.email) {
    saveProfileByEmail(user.email, user);
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function isLoggedIn() {
  return !!localStorage.getItem(TOKEN_KEY);
}

export function clearUser() {
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(TOKEN_KEY);
}

export function getProfileByEmail(email) {
  const profiles = JSON.parse(localStorage.getItem(PROFILES_KEY) || '{}');
  return profiles[email.toLowerCase().trim()] || null;
}

export function saveProfileByEmail(email, user) {
  const profiles = JSON.parse(localStorage.getItem(PROFILES_KEY) || '{}');
  profiles[email.toLowerCase().trim()] = user;
  localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
}

const ASHITA_PROFILE = {
  name: 'Ashita Singh',
  email: 'ashita.singh@gmail.com',
  phone: '+1 (310) 555-0199',
  familyMembers: [
    { id: 1, name: 'Raj Singh', relation: 'Spouse', phone_number: '+1 (310) 555-0200' },
    { id: 2, name: 'Priya Singh', relation: 'Daughter', phone_number: '' },
  ],
  contacts: [
    { id: 1, name: 'Dr. Patel', role: 'Primary Care', org: 'UCLA Health', phone: '(310) 555-0301' },
  ],
  providers: [
    { id: 1, name: 'Dr. Patel', specialty: 'Primary Care', practice: 'UCLA Health' },
  ],
  preferences: {
    communicationStyle: 'brief',
    preferredContact: 'text',
    callUrgencyThreshold: 'high',
    quietHoursStart: '21:00',
    quietHoursEnd: '07:00',
    keepFreeStart: '20:00',
    keepFreeEnd: '08:00',
    activeDays: ['mon', 'tue', 'wed', 'thu', 'fri'],
    morningDigest: true,
    digestTime: '07:30',
    digestContent: 'calendar+tasks',
    digestTravelTime: true,
    escalationTimeoutMinutes: 30,
    autoApproveLowRisk: true,
    maxReminders: 3,
    tone: 'casual',
    reminderLeadTime: '30',
    conflictHandling: 'suggest',
  },
  bannerDismissed: true,
};

// Seeds demo profiles into localStorage on first app load.
export function ensureDemoProfiles() {
  const profiles = JSON.parse(localStorage.getItem(PROFILES_KEY) || '{}');
  const key = ASHITA_PROFILE.email.toLowerCase();
  if (!profiles[key]) {
    profiles[key] = ASHITA_PROFILE;
    localStorage.setItem(PROFILES_KEY, JSON.stringify(profiles));
  }
}
