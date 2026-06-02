// main onboarding form, ties together google auth and preferences
// this is basically the whole frontend lol
// we should also add login page after all basic on boarding is done. This should be a new file later.

import { useState } from "react";

export default function RegistrationForm({ onSuccess }) {
    const [phone, setPhone] = useState("");
    const [email, setEmail] = useState("");
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e) {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            await onSuccess(phone, email);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <form onSubmit={handleSubmit}>
            <h2>Create your account</h2>
            <div>
                <label>
                    Phone number
                    <input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="+13105550199"
                        required
                    />
                </label>
            </div>
            <div>
                <label>
                    Email (optional)
                    <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                    />
                </label>
            </div>
            {error && <p style={{ color: "red" }}>{error}</p>}
            <button type="submit" disabled={loading}>
                {loading ? "Creating account..." : "Next"}
            </button>
        </form>
    );
}
