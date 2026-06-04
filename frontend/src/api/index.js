// axios base instance, all api calls go thru here
// sets base url to backend, handles errors in one place

// Local dev: '/api' -> vite proxies to localhost backend.
// Prod (Vercel): VITE_API_BASE_URL + '/api' hits the Railway backend.
const BASE = `${import.meta.env.VITE_API_BASE_URL || ''}/api`;

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
