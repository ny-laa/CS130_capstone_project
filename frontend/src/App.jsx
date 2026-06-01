import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import NavBar from './components/NavBar';
import Profile from './pages/Profile';
import Conversations from './pages/Conversations';
import Tasks from './pages/Tasks';
import Register from './pages/Register';
import SignUp from './pages/SignUp';
import Step1Family from './pages/Onboard/Step1Family';
import Step2Preferences from './pages/Onboard/Step2Preferences';

// [GenAI Use] LLM Response Start
// New routes added for /signup, /onboard/step1, /onboard/step2.
// NavBar hidden on /signup and /onboard/* paths.
// [GenAI Use] LLM Response End
// [GenAI Use] Reflection: NavBar hiding uses location.pathname check
// which is the standard pattern for route-based layout control in 
// React Router. Confirmed existing routes (/tasks, /conversations, 
// /profile) were not broken. Verified /onboard/* wildcard correctly 
// hides NavBar on both step1 and step2.
// Consulted: https://reactrouter.com/en/main/hooks/use-location

const AUTH_PATHS = ['/signup', '/onboard'];

function AppContent() {
  const { pathname } = useLocation();
  const hideNav = AUTH_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'));

  return (
    <div className={hideNav ? '' : 'app-layout'}>
      {!hideNav && <NavBar />}
      <main className={hideNav ? '' : 'main-content'}>
        <Routes>
          <Route path="/" element={<Navigate to="/tasks" replace />} />
          <Route path="/signup" element={<SignUp />} />
          <Route path="/onboard/step1" element={<Step1Family />} />
          <Route path="/onboard/step2" element={<Step2Preferences />} />
          <Route path="/register" element={<Register />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/conversations" element={<Conversations />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
