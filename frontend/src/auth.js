const USER_KEY = 'g_user';

export function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function isLoggedIn() {
  return !!localStorage.getItem(USER_KEY);
}

export function clearUser() {
  localStorage.removeItem(USER_KEY);
}
