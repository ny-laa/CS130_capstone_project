// button that kicks off the google oauth flow
// clicking this redirects to googles auth page to get calendar and gmail perms
// Used these docs: https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid
// https://developers.google.com/identity/gsi/web/guides/display-button#javascript
// https://vite.dev/guide/env-and-mode

import {useEffect} from "react";

function GoogleSignOn() {
    useEffect(() => {
        const clientID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
        function handleCredentialResponse(response) {
            console.log("Encoded JWT token: " + response.credential);
        }
        window.google.accounts.id.initialize({
            client_id: clientID,
            callback: handleCredentialResponse
        });
        window.google.accounts.id.renderButton(
            document.getElementById("buttonDiv"),
            { theme: "outline", size: "large" }
        );
    },[]);
    return(
        <div id="buttonDiv"></div>
    )
}

export default GoogleSignOn