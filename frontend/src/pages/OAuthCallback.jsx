// Used GenAI to help me with the layout for this page (knowledgable intern method)
import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { setUser, setToken } from '../auth';

export default function OAuthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const userId = params.get('user_id');
    const email = params.get('email');
    const name = params.get('name');
    const token = params.get('token');
    const isNewUser = params.get('new_user') === 'true';

    if (userId && email && token) {
      setUser({
        id: userId,
        email,
        name: name || '',
      });

      setToken(token);

      if (isNewUser) {
        navigate('/onboard/step1', { replace: true });
      } else {
        navigate('/tasks', { replace: true });
      }
    } else {
      navigate('/signin', { replace: true });
    }
  }, [params, navigate]);

  return <p>Signing you in...</p>;
}