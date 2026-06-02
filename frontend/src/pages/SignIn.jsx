import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { isLoggedIn, setToken, setUser } from '../auth';
import { login } from '../api';

export default function SignIn() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) navigate('/tasks', { replace: true });
  }, [navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.email.trim() || !form.password) { setError('Please fill in all fields.'); return; }

    setSubmitting(true);
    setError('');
    try {
      const { user, token } = await login(form.email.trim(), form.password);
      setUser(user);
      setToken(token);
      navigate('/tasks');
    } catch {
      setError('Invalid email or password.');
    } finally {
      setSubmitting(false);
    }
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
