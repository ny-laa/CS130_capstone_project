import { NavLink, Link } from 'react-router-dom';
import { clearUser } from '../auth';

// [GenAI Use] LLM Response Start
// NavBar with NAV_ITEMS, NavLink active class styling
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Confirmed NavLink isActive callback works 
// correctly. Consulted: https://reactrouter.com/en/main/components/nav-link#classname
// Placeholder icons and brand name still need updating.

const NAV_ITEMS = [
  { to: '/tasks', label: 'Tasks', icon: '✓' },
  { to: '/conversations', label: 'History', icon: '◎' },
  { to: '/profile', label: 'Profile', icon: '⊙' },
];

export default function NavBar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">G</div>
      <ul className="navbar-links">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}
            >
              <span className="nav-icon">{icon}</span>
              <span className="nav-label">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <Link to="/signup" className="navbar-signup" onClick={clearUser}>Sign Up</Link>
    </nav>
  );
}
