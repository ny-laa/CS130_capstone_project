import { NavLink, Link } from 'react-router-dom';
import { clearUser } from '../auth';

// [GenAI Use] LLM Response Start
// NavBar with NAV_ITEMS, NavLink active class styling
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Confirmed NavLink isActive callback works 
// correctly. Consulted: https://reactrouter.com/en/main/components/nav-link#classname
// Placeholder icons and brand name still need updating.

// [GenAI Use] LLM Response Start
// Chat icon added between Tasks and History. Red badge shows count
// of ESCALATION_PENDING tasks.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: Badge count reads from TaskContext so it
// updates in real time when a task status changes. Badge is hidden
// when count is 0. Checked the chat nav item highlights correctly
// when on the /chat route.

  const NAV_ITEMS = [
    { to: '/tasks', label: 'Tasks', icon: '✓' },
    { to: '/conversations', label: 'History', icon: '◎' },
    { to: '/profile', label: 'Profile', icon: '⊙' },
  ];

  return (
    <nav className="navbar">
      <div className="navbar-brand">G</div>
      <ul className="navbar-links">
        {NAV_ITEMS.map(({ to, label, icon, badge }) => (
          <li key={to}>
            <NavLink
              to={to}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              <span className="nav-icon">{icon}</span>
              <span className="nav-label">{label}</span>
              {badge > 0 && <span className="nav-badge">{badge}</span>}
            </NavLink>
          </li>
        ))}
      </ul>
      <Link to="/signup" className="navbar-signup" onClick={clearUser}>
        Sign Up
      </Link>
    </nav>
  );
}
