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

// fetch the conversation history for a user (audit log of inbound + outbound
// sms / voice). returns [{id, content, direction, channel, timestamp, task_id}]
// newest first. used by the conversations page once the UI rewrite lands.
export function getMessages(userId, limit = 50) {
    return apiFetch(`/users/${userId}/messages?limit=${limit}`);
}
