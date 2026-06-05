import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { isLoggedIn } from '../auth';
import GoogleSignOn from '../components/registration/GoogleAuthButton';

export default function SignIn() {
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoggedIn()) navigate('/tasks', { replace: true });
  }, [navigate]);

  return (
    <div className="signup-page">
      <div className="signup-card">
        <div className="signup-logo">G</div>
        <p className="signup-tagline">The only assistant you will need!</p>
        <GoogleSignOn mode="signin" />
      </div>
    </div>
  );
}