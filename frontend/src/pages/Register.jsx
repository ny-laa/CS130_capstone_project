// the registration/onboarding page
// this is basically the only page in the whole frontend, just for setup

import { useState } from "react";
import { registerUser, updatePreferences } from "../api/auth.js";
import RegistrationForm from "../components/registration/RegistrationForm";
import PreferencesForm from "../components/registration/PreferencesForm";
import GoogleSignOn from "../components/registration/GoogleAuthButton";

export default function Register() {
    const [step, setStep] = useState(1);
    const [userId, setUserId] = useState(null);

    async function handleRegistration(phone, email) {
        const user = await registerUser(phone, email);
        setUserId(user.id);
        setStep(2);
    }

    async function handlePreferences(prefs) {
        await updatePreferences(userId, prefs);
        setStep(3);
    }

    return (
        <div>
            <h1>Set up G</h1>
            {step === 1 && <RegistrationForm onSuccess={handleRegistration} />}
            {step === 2 && <PreferencesForm onSuccess={handlePreferences} />}
            {step === 3 && (
                <div>
                    <h2>Connect Google</h2>
                    <p>Link your Google account so G can access your calendar and Gmail.</p>
                    <GoogleSignOn />
                </div>
            )}
        </div>
    );
}
