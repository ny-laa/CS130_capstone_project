// the registration/onboarding page
// this is basically the only page in the whole frontend, just for setup

import React, { useState } from "react";
import GoogleSignOn from "../components/registration/GoogleAuthButton";

export default function Register() {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const handleSubmit = (e) => {
        e.preventDefault();
        
        console.log({
            name,
            email
        });
    };

    return (
        <div>
            <h1>Make an Account</h1>
            <GoogleSignOn/>
        </div>
    )
}