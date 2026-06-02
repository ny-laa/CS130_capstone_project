// axios base instance, all api calls go thru here
// sets base url to backend, handles errors in one place

const BASE = '/api';

export async function apiFetch(path, options = {}) {
    const res = await fetch(`${BASE}${path}`, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Request failed: ${res.status}`);
    }
    return res.json();
}
