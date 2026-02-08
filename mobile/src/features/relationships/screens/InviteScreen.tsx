import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAcceptInviteMutation, useContactLookupMutation } from '../api/relationshipQueries';
import { authClient } from '../../auth/api/authClient';
import { useSessionStore } from '../../auth/store/sessionStore';
import { AuthScreen } from '../../../../components/AuthScreen';

type InviteState = 'validating' | 'valid' | 'invalid' | 'accepting' | 'accepted';

export const InviteScreen: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<InviteState>('validating');
  const [inviteData, setInviteData] = useState<{
    email?: string;
    relationship_type?: string;
    inviter_name?: string;
  } | null>(null);
  
  const acceptInviteMutation = useAcceptInviteMutation();
  const { setUser } = useSessionStore();

  useEffect(() => {
    if (!token) {
      setState('invalid');
      return;
    }

    // Validate token
    const validateToken = async () => {
      try {
        const response = await authClient.validateInviteToken(token);
        setInviteData(response.data);
        setState('valid');
      } catch (error) {
        console.error('Invalid invite token:', error);
        setState('invalid');
      }
    };

    validateToken();
  }, [token]);

  const handleSignup = async (email: string, password: string, displayName: string) => {
    setState('accepting');
    try {
      // Signup with invite token
      await authClient.signup(email, password, displayName, token);
      
      // Accept invite (if needed)
      if (token) {
        await acceptInviteMutation.mutateAsync(token);
      }

      // Load user and redirect
      const userResponse = await authClient.getCurrentUser();
      const userData = userResponse.data;
      
      // Update session store
      setUser({
        id: userData.id,
        name: userData.display_name || email.split('@')[0],
        lovedOnes: [],
        // Map other fields as needed
      } as any);

      setState('accepted');
      navigate('/dashboard');
    } catch (error) {
      console.error('Failed to accept invite:', error);
      setState('valid'); // Return to signup form
      alert('Failed to create account. Please try again.');
    }
  };

  if (state === 'validating') {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto mb-4"></div>
          <p className="text-sm text-slate-500">Validating invite...</p>
        </div>
      </div>
    );
  }

  if (state === 'invalid') {
    return (
      <div className="h-screen flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <h2 className="text-2xl font-black text-slate-900 mb-4">Invalid Invite</h2>
          <p className="text-sm text-slate-600 mb-6">
            This invite link is invalid or has expired. Please request a new invite.
          </p>
          <button
            onClick={() => navigate('/auth')}
            className="bg-slate-900 text-white px-6 py-3 font-bold uppercase tracking-widest text-xs"
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  if (state === 'accepted') {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-sm text-slate-500">Redirecting to dashboard...</p>
        </div>
      </div>
    );
  }

  // Show signup form with invite context
  return (
    <AuthScreen
      onSignup={handleSignup}
      onLogin={(email) => {
        // If user already exists, they can login
        navigate('/auth');
      }}
      inviteToken={token || undefined}
      inviteEmail={inviteData?.email}
      inviteRelationshipType={inviteData?.relationship_type}
      inviterName={inviteData?.inviter_name}
    />
  );
};
