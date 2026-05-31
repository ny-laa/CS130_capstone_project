// functions for talking to the backend auth and registration endpoints
// like submitting the onboarding form, initiating google oauth etc

import { apiFetch } from './index.js';

export function registerUser(phone_number, email) {
    return apiFetch('/users', {
        method: 'POST',
        body: JSON.stringify({ phone_number, email: email || undefined }),
    });
}

export function updatePreferences(userId, prefs) {
    return apiFetch(`/users/${userId}/preferences`, {
        method: 'PATCH',
        body: JSON.stringify(prefs),
    });
}
