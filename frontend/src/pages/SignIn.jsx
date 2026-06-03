import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { isLoggedIn, setToken, setUser, getProfileByEmail } from '../auth';

export default function SignIn() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) navigate('/tasks', { replace: true });
  }, [navigate]);

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.email.trim() || !form.password) { setError('Please fill in all fields.'); return; }

    setSubmitting(true);
    const email = form.email.trim();
    const saved = getProfileByEmail(email);

    if (saved) {
      setUser(saved);
      setToken('demo-token');
      navigate('/tasks');
    } else {
      // No existing profile — derive a display name from the email prefix.
      const prefix = email.split('@')[0];
      const name = prefix
        .replace(/[._-]/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
      const newUser = {
        name,
        email,
        phone: '',
        familyMembers: [],
        contacts: [],
        providers: [],
        preferences: null,
        bannerDismissed: false,
      };
      setUser(newUser);
      setToken('demo-token');
      navigate('/tasks');
    }
    setSubmitting(false);
  }

  function set(field) {
    return (e) => { setError(''); setForm((f) => ({ ...f, [field]: e.target.value })); };
  }

  return (
    <div className="signup-page">
      <div className="signup-card">
        <div className="signup-logo">G</div>
        <p className="signup-tagline">Welcome back.</p>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <input
              className="auth-input"
              type="email"
              placeholder="Email"
              value={form.email}
              onChange={set('email')}
              autoComplete="email"
            />
          </div>

          <div className="auth-field">
            <input
              className="auth-input"
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={set('password')}
              autoComplete="current-password"
            />
            {error && <p className="auth-error">{error}</p>}
          </div>

          <button className="auth-btn" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="signup-footer">
          Don't have an account?{' '}
          <Link to="/signup" className="link-btn">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
