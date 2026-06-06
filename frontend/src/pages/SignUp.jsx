import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { isLoggedIn } from '../auth';
import GoogleSignOn from '../components/registration/GoogleAuthButton';

export default function SignUp() {
  const navigate = useNavigate();

  useEffect(() => {
    if (isLoggedIn()) navigate('/tasks', { replace: true });
  }, [navigate]);

  return (
    <div className="signup-page">
      <div className="signup-card">
        <div className="signup-logo">G</div>
        <p className="signup-tagline">Create your G account with Google.</p>

        <GoogleSignOn mode="signup" />

        <p className="signup-footer">
          Already have an account?{' '}
          <Link to="/signin" className="link-btn">Sign in</Link>
        </p>
      </div>
    </div>
  );
}