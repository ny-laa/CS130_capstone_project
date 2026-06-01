import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { setUser, isLoggedIn } from '../auth';

// [GenAI Use] LLM Response Start
// G logo, "Continue with Google" (routes to /onboard/step1), 
// "Sign in" (routes to /profile directly)
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: "Continue with Google" stores partial user 
// in g_onboard key then navigates to step 1. "Sign in" skips onboarding
// entirely and goes straight to /profile. Verified NavBar is hidden on 
// /signup per App.jsx update so the page is clean with no nav clutter.
// Google button is visual only for now - real GSI flow needs 
// VITE_GOOGLE_CLIENT_ID set.

const MOCK_BASE = {
  email: 'user@gmail.com',
  familyMembers: [],
  contacts: [],
  providers: [],
  preferences: {
    communicationStyle: 'brief',
    preferredContact: 'text',
    tone: 'casual',
    morningDigest: false,
    digestTime: '07:00',
    digestContent: 'calendar',
    digestTravelTime: false,
    keepFreeStart: '',
    keepFreeEnd: '',
    quietHoursStart: '22:00',
    quietHoursEnd: '07:00',
    reminderLeadTime: '30',
    autoApproveLowRisk: false,
    escalationTimeoutMinutes: 30,
    activeDays: ['mon', 'tue', 'wed', 'thu', 'fri'],
    callUrgencyThreshold: 'high',
    maxReminders: 3,
    conflictHandling: 'suggest',
  },
};

export default function SignUp() {
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoggedIn()) navigate('/profile', { replace: true });
  }, [navigate]);

  function handleGoogleSignIn() {
    localStorage.setItem('g_onboard', JSON.stringify({ ...MOCK_BASE, name: '', phone: '' }));
    navigate('/onboard/step1');
  }

  function handleSignIn() {
    setUser({
      ...MOCK_BASE,
      name: 'Alex Johnson',
      phone: '+1 (310) 555-0182',
      bannerDismissed: true,
      preferences: {
        ...MOCK_BASE.preferences,
        morningDigest: true,
        digestTime: '08:00',
        digestContent: 'calendar+email',
        autoApproveLowRisk: true,
        tone: 'casual',
        reminderLeadTime: '60',
        escalationTimeoutMinutes: 30,
        quietHoursStart: '22:00',
        quietHoursEnd: '07:00',
        keepFreeStart: '09:00',
        keepFreeEnd: '17:00',
      },
    });
    navigate('/profile');
  }

  return (
    <div className="signup-page">
      <div className="signup-card">
        <div className="signup-logo">G</div>
        <p className="signup-tagline">Your AI secretary, over text.</p>
        <button className="btn-google" onClick={handleGoogleSignIn}>
          <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908C16.658 14.39 17.64 12.08 17.64 9.2z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
            <path d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Continue with Google
        </button>
        <p className="signup-footer">
          Already have an account?{' '}
          <button className="link-btn" onClick={handleSignIn}>Sign in</button>
        </p>
      </div>
    </div>
  );
}
