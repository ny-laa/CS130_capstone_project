// button that kicks off the google oauth flow
// clicking this redirects to googles auth page to get calendar and gmail perms
// Used these docs: https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
// https://developers.google.com/identity/gsi/web/guides/display-button#javascript
// https://vite.dev/guide/env-and-mode
// Update: used Claude to understand that I need to use oauth2 instead to have persistent tokens

import {useEffect, useRef} from "react";

// Used Claude to get the correct access/scope
const ACCESS = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
].join(" ");

function GoogleSignOn() {
    const curClient = useRef(null);

    useEffect(() => {
        // to make tokens persist for calender/mail, add outh2
        const initClient = () => {
            const client_id = import.meta.env.VITE_GOOGLE_CLIENT_ID;
            curClient.current = window.google.accounts.oauth2.initCodeClient({
                client_id, 
                scope: ACCESS,
                ux_mode: "redirect",
                redirect_uri: `${import.meta.env.VITE_API_BASE_URL}/oauth/google`,
                access_type: "offline",
                prompt: "consent",
            });
        };
        if (window.google?.accounts?.oauth2){
            initClient();
        }
        else {
            window.addEventListener("load", initClient);
            return () => window.removeEventListener("load", initClient);
        }
    }, []);

    const handleClick = () => {
        curClient.current?.requestCode();
    };
    return(
        <div style={{ marginTop: '12px', marginBottom: '12px'}}>
            <button className="auth-btn auth-btn--google" onClick={handleClick}>Sign In with Google</button>
        </div>
    )
}

export default GoogleSignOn