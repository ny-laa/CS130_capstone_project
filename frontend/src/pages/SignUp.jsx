import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { isLoggedIn, setToken } from '../auth';

export default function SignUp() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) navigate('/tasks', { replace: true });
  }, [navigate]);

  function validate() {
    const e = {};
    if (!form.name.trim()) e.name = 'Name is required.';
    if (!form.email.trim()) e.email = 'Email is required.';
    if (!form.password) e.password = 'Password is required.';
    else if (form.password.length < 8) e.password = 'Password must be at least 8 characters.';
    if (form.password !== form.confirm) e.confirm = 'Passwords do not match.';
    return e;
  }

  function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setSubmitting(true);
    // Store name + email in onboard scratch so Step1Family can pre-populate them.
    localStorage.setItem('g_onboard', JSON.stringify({
      name: form.name.trim(),
      email: form.email.trim(),
    }));
    setToken('demo-token');
    navigate('/onboard/step1');
    setSubmitting(false);
  }

  function set(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  return (
    <div className="signup-page">
      <div className="signup-card">
        <div className="signup-logo">G</div>
        <p className="signup-tagline">Your AI secretary, over text.</p>

        {errors.form && <p className="auth-error auth-error--banner">{errors.form}</p>}

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <input
              className={`auth-input${errors.name ? ' auth-input--error' : ''}`}
              type="text"
              placeholder="Full name"
              value={form.name}
              onChange={set('name')}
              autoComplete="name"
            />
            {errors.name && <p className="auth-error">{errors.name}</p>}
          </div>

          <div className="auth-field">
            <input
              className={`auth-input${errors.email ? ' auth-input--error' : ''}`}
              type="email"
              placeholder="Email"
              value={form.email}
              onChange={set('email')}
              autoComplete="email"
            />
            {errors.email && <p className="auth-error">{errors.email}</p>}
          </div>

          <div className="auth-field">
            <input
              className={`auth-input${errors.password ? ' auth-input--error' : ''}`}
              type="password"
              placeholder="Password"
              value={form.password}
              onChange={set('password')}
              autoComplete="new-password"
            />
            {errors.password && <p className="auth-error">{errors.password}</p>}
          </div>

          <div className="auth-field">
            <input
              className={`auth-input${errors.confirm ? ' auth-input--error' : ''}`}
              type="password"
              placeholder="Confirm password"
              value={form.confirm}
              onChange={set('confirm')}
              autoComplete="new-password"
            />
            {errors.confirm && <p className="auth-error">{errors.confirm}</p>}
          </div>

          <button className="auth-btn" type="submit" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="signup-footer">
          Already have an account?{' '}
          <Link to="/signin" className="link-btn">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
