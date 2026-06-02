// form section for setting user preferences
// comm_style (brief/detailed), preferred_channel (sms/call), blocked_windows etc
// connects to postgres via the backend api

import { useState } from "react";

export default function PreferencesForm({ onSuccess }) {
    const [commStyle, setCommStyle] = useState("brief");
    const [channel, setChannel] = useState("sms");
    const [quietStart, setQuietStart] = useState("");
    const [quietEnd, setQuietEnd] = useState("");
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e) {
        e.preventDefault();
        setError(null);
        setLoading(true);

        const blocked_windows =
            quietStart && quietEnd
                ? [{ start_time: quietStart, end_time: quietEnd }]
                : null;

        try {
            await onSuccess({
                comm_style: commStyle,
                preferred_channel: channel,
                blocked_windows,
            });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <form onSubmit={handleSubmit}>
            <h2>Your preferences</h2>

            <fieldset>
                <legend>Communication style</legend>
                <label>
                    <input
                        type="radio"
                        value="brief"
                        checked={commStyle === "brief"}
                        onChange={() => setCommStyle("brief")}
                    />
                    Brief — short, to the point
                </label>
                <label>
                    <input
                        type="radio"
                        value="detailed"
                        checked={commStyle === "detailed"}
                        onChange={() => setCommStyle("detailed")}
                    />
                    Detailed — full context
                </label>
            </fieldset>

            <fieldset>
                <legend>Preferred contact channel</legend>
                <label>
                    <input
                        type="radio"
                        value="sms"
                        checked={channel === "sms"}
                        onChange={() => setChannel("sms")}
                    />
                    Text (SMS)
                </label>
                <label>
                    <input
                        type="radio"
                        value="call"
                        checked={channel === "call"}
                        onChange={() => setChannel("call")}
                    />
                    Phone call
                </label>
            </fieldset>

            <fieldset>
                <legend>Quiet hours (optional)</legend>
                <label>
                    From
                    <input
                        type="time"
                        value={quietStart}
                        onChange={(e) => setQuietStart(e.target.value)}
                    />
                </label>
                <label>
                    To
                    <input
                        type="time"
                        value={quietEnd}
                        onChange={(e) => setQuietEnd(e.target.value)}
                    />
                </label>
            </fieldset>

            {error && <p style={{ color: "red" }}>{error}</p>}
            <button type="submit" disabled={loading}>
                {loading ? "Saving..." : "Next"}
            </button>
        </form>
    );
}
