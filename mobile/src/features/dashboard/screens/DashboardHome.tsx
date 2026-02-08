import React, { useRef, useState, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import { AppMode, LovedOne, AddNotificationFn } from '../../../shared/types/domain';
import { Ruler, Bell, X, Loader2, Copy, Share2 } from 'lucide-react';
import { ActiveUnitsTray } from '@/src/features/dashboard/components/ActiveUnitsTray';
import { FloorPlan } from '@/src/features/dashboard/components/FloorPlan';
import { NotificationCenterPanel } from '@/src/features/dashboard/components/NotificationCenterPanel';
import { AddRelationshipModal } from '@/src/features/dashboard/components/AddRelationshipModal';
import { ReactionMenu } from '@/src/features/dashboard/components/ReactionMenu';
import { PersonalProfilePanel } from '../../profile/screens/PersonalProfilePanel';
import { useRealtimeStore } from '../../../stores/realtime.store';
import { useUiStore } from '../../../stores/ui.store';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import { apiService } from '../../../shared/api/apiService';

interface DashboardHomeProps {
  onRoomClick: (mode: AppMode) => void;
  onRestrictedAccess: (mode: AppMode) => void;
  onUpdateProfile: (user: any) => void;
  onUpdateLovedOne: (id: string, updates: Partial<LovedOne>) => void;
  onAddRelationship: (email: string, relationship: string) => Promise<void>;
  onRemoveRelationship: (id: string) => Promise<void>;
  onLogout: () => void;
  onEditProfile: () => void;
  sendReaction: (emoji: string) => Promise<void>;
  onAddNotification?: AddNotificationFn;
}

export const DashboardHome: React.FC<DashboardHomeProps> = ({
  onRoomClick,
  onRestrictedAccess,
  onUpdateProfile,
  onUpdateLovedOne,
  onAddRelationship,
  onRemoveRelationship,
  onLogout,
  onEditProfile,
  sendReaction,
  onAddNotification,
}) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  const { notifications } = useRealtimeStore();
  const {
    showSidePanel,
    showPersonalProfilePanel,
    toggleSidePanel,
    toggleProfilePanel,
    openToNotificationId,
    setActivitiesOpenToTab,
    isAddingUnit,
    setIsAddingUnit,
    isAddingUnitLoading,
    newUnitEmail,
    setNewUnitEmail,
    newUnitRel,
    setNewUnitRel,
    reactionMenuTarget,
    setReactionMenuTarget,
    menuPosition,
    setMenuPosition,
  } = useUiStore();
  
  if (!user) {
    return null; // Should not happen, but guard against it
  }
  
  // Use relationships from store, fallback to user.lovedOnes
  const availableLovedOnes = relationships.length > 0 ? relationships : user.lovedOnes;
  const longPressTimer = useRef<NodeJS.Timeout | null>(null);
  const isLongPress = useRef(false);

  // Invite link modal (for pending units in tray)
  const [inviteLinkModal, setInviteLinkModal] = useState<{
    person: LovedOne | null;
    url: string | null;
    loading: boolean;
    error: string | null;
  }>({ person: null, url: null, loading: false, error: null });

  const handleInviteLinkRequest = useCallback(async (person: LovedOne) => {
    if (!person.relationshipId || !person.inviteId) {
      onAddNotification?.('system', 'Invite link', 'No invite link available for this pending user.');
      return;
    }
    setInviteLinkModal({ person, url: null, loading: true, error: null });
    try {
      const res = await apiService.getInviteLink(person.relationshipId, person.inviteId);
      const url = (res.data as { invite_url: string }).invite_url;
      setInviteLinkModal((prev) => ({ ...prev, url, loading: false }));
    } catch (err: any) {
      setInviteLinkModal((prev) => ({
        ...prev,
        loading: false,
        error: err?.message || 'Failed to get invite link',
      }));
    }
  }, [onAddNotification]);

  const closeInviteLinkModal = useCallback(() => {
    setInviteLinkModal({ person: null, url: null, loading: false, error: null });
  }, []);

  const copyInviteLink = useCallback(async () => {
    if (!inviteLinkModal.url) return;
    try {
      await navigator.clipboard.writeText(inviteLinkModal.url);
      useUiStore.getState().setToast?.('Link copied');
    } catch {
      const ta = document.createElement('textarea');
      ta.value = inviteLinkModal.url;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        useUiStore.getState().setToast?.('Link copied');
      } finally {
        document.body.removeChild(ta);
      }
    }
  }, [inviteLinkModal.url]);

  const shareInviteLink = useCallback(async () => {
    if (!inviteLinkModal.url || !inviteLinkModal.person) return;
    const isNative = Capacitor.isNativePlatform();
    if (isNative) {
      try {
        const { Share } = await import('@capacitor/share');
        await Share.share({
          title: `Join my ${inviteLinkModal.person.relationship} relationship on Project Inside`,
          text: `${user.name} has invited you to connect. Accept: ${inviteLinkModal.url}`,
          url: inviteLinkModal.url,
          dialogTitle: 'Share Invitation',
        });
      } catch (e) {
        console.warn('Share failed', e);
        copyInviteLink();
      }
    } else {
      copyInviteLink();
    }
  }, [inviteLinkModal.url, inviteLinkModal.person, user.name, copyInviteLink]);

  const handleUnitPointerDown = (e: React.PointerEvent, person: LovedOne) => {
    isLongPress.current = false;
    const x = e.clientX;
    const y = e.clientY;

    longPressTimer.current = setTimeout(() => {
      isLongPress.current = true;
      setReactionMenuTarget({ id: person.id, name: person.name, relationshipId: person.relationshipId });
      setMenuPosition({ x, y });
      if (navigator.vibrate) navigator.vibrate(50);
    }, 500);
  };

  const handleUnitPointerUp = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const handleUnitPointerLeave = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const handleReaction = async (emoji: string) => {
    await sendReaction(emoji);
    setReactionMenuTarget(null);
    setMenuPosition(null);
  };

  const handleCloseReactionMenu = () => {
    setReactionMenuTarget(null);
    setMenuPosition(null);
  };

  const togglePref = (key: 'notifications' | 'hapticFeedback' | 'privacyMode') => {
    const defaultPrefs = { notifications: true, hapticFeedback: true, privacyMode: false, shareData: true };
    const currentPrefs = user.preferences || defaultPrefs;
    const newPrefs = { ...currentPrefs, [key]: !currentPrefs[key] };
    onUpdateProfile({ ...user, preferences: newPrefs });
  };
  const preferences = {
    notifications: user.preferences?.notifications ?? true,
    hapticFeedback: user.preferences?.hapticFeedback ?? true,
    privacyMode: user.preferences?.privacyMode ?? false,
  };

  return (
    <>
      {/* Personal Profile Panel */}
      {showPersonalProfilePanel && (
        <PersonalProfilePanel
          onClose={() => toggleProfilePanel(false)}
          onUpdateProfile={onUpdateProfile}
          onEditProfile={onEditProfile}
          onLogout={onLogout}
        />
      )}
      
      <div className="app-shell h-screen bg-white p-0 flex flex-col relative overflow-hidden" style={{ height: '100vh', width: '100vw' }}>
        {/* Background grid */}
        <div className="absolute inset-0 z-0 pointer-events-none opacity-20" style={{ backgroundImage: 'linear-gradient(#1e293b 1px, transparent 1px), linear-gradient(90deg, #1e293b 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
        <div className="absolute inset-0 z-0 pointer-events-none opacity-10" style={{ backgroundImage: 'linear-gradient(#1e293b 2px, transparent 2px), linear-gradient(90deg, #1e293b 2px, transparent 2px)', backgroundSize: '100px 100px' }}></div>
        
        {/* Header */}
        <header className="relative z-20 px-6 pt-6 pb-4 flex justify-between items-start bg-white/80 backdrop-blur-sm border-b-4 border-slate-900">
          <div>
            <div className="flex items-center gap-2 text-slate-500 text-[10px] font-mono font-bold uppercase tracking-widest mb-1">
              <Ruler size={12} />
              <span>Project: Inside</span>
            </div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tighter leading-none">THE LOBBY</h1>
            <p className="text-[10px] font-mono text-slate-400 mt-1">LVL 1 • GENERAL ARRANGEMENT</p>
          </div>

          <div className="flex items-center gap-4 mt-1">
            <div className="flex items-center gap-3">
              <div className="text-right hidden sm:block">
                <div className="text-xs font-bold uppercase tracking-widest text-slate-900">{user.name}</div>
                <div className="text-[10px] font-mono text-slate-400 uppercase">CMD: ONLINE</div>
              </div>
              <button
                onClick={() => toggleProfilePanel(true)}
                className={`w-16 h-16 border-2 border-slate-900 flex items-center justify-center font-bold text-2xl shadow-[4px_4px_0px_rgba(30,41,59,0.2)] transition-colors cursor-pointer active:scale-95 overflow-hidden ${
                  user.profilePicture 
                    ? 'bg-white' 
                    : 'bg-slate-900 text-white hover:bg-slate-800'
                }`}
                title="Personal Profile"
              >
                {user.profilePicture ? (
                  <img 
                    src={user.profilePicture} 
                    alt={user.name} 
                    className="w-full h-full object-cover"
                  />
                ) : (
                  user.name.charAt(0)
                )}
              </button>
            </div>
          </div>
        </header>

        {/* Active Units Tray */}
        <ActiveUnitsTray
          lovedOnes={availableLovedOnes}
          currentUserId={user.id}
          onAddUnit={() => setIsAddingUnit(true)}
          onLongPress={(person, position) => {
            setReactionMenuTarget({ id: person.id, name: person.name, relationshipId: person.relationshipId });
            setMenuPosition(position);
          }}
          onInviteLinkRequest={handleInviteLinkRequest}
        />

        {/* Main Content Area */}
        <div className={`flex-1 flex flex-col relative transition-transform duration-300 ease-in-out ${showSidePanel ? '-translate-x-16 opacity-50' : ''}`}>
          <div 
            className="flex-1 w-full relative min-h-0"
            style={{ 
              minHeight: 0, 
              width: '100%', 
              height: '100%',
              display: 'flex',
              alignItems: 'stretch',
              justifyContent: 'center',
              padding: '8px',
              overflowX: 'hidden',
              overflowY: 'auto',
              WebkitOverflowScrolling: 'touch',
            }}
          >
            <FloorPlan 
              onRoomClick={onRoomClick}
              onRestrictedAccess={onRestrictedAccess}
            />
          </div>
        </div>

        {/* Notification Center Button — same position as original System Config in inside/App.tsx (floating lower right) */}
        <button
          onClick={() => toggleSidePanel(true)}
          className="fixed bottom-6 right-6 z-30 w-8 h-8 bg-white text-slate-900 border-2 border-slate-900 shadow-[2px_2px_0px_rgba(30,41,59,1)] flex items-center justify-center hover:bg-slate-50 transition-all active:translate-y-0.5 active:shadow-none"
          style={{ bottom: 'max(1.5rem, calc(1.5rem + env(safe-area-inset-bottom, 0px)))', right: 'max(1.5rem, calc(1.5rem + env(safe-area-inset-right, 0px)))' }}
          title="Notification Center"
        >
          <Bell size={14} />
          {(() => {
            const unreadCount = notifications.filter((n) => !n.read).length;
            return unreadCount > 0 ? (
              <span className="absolute -top-2 -right-2 w-5 h-5 bg-rose-600 text-white text-[10px] font-black flex items-center justify-center border-2 border-white">
                {Math.min(unreadCount, 99)}
              </span>
            ) : null;
          })()}
        </button>

        {/* Notification Center Panel (notifications + settings views, like inside/App.tsx) */}
        <NotificationCenterPanel
          isOpen={showSidePanel}
          onClose={() => toggleSidePanel(false)}
          openToNotificationId={openToNotificationId}
          onNotificationClick={(notification) => {
            toggleSidePanel(false);
            if (notification.type === 'activity_invite') {
              onRoomClick(AppMode.ACTIVITIES);
              setActivitiesOpenToTab('planned');
            }
            if (notification.type === 'lounge_invite') {
              onRoomClick(AppMode.LOUNGE);
            }
          }}
          onLogout={onLogout}
          onEditProfile={() => { toggleSidePanel(false); onEditProfile(); }}
          preferences={preferences}
          onTogglePreference={togglePref}
          user={user}
        />

        {/* Add Relationship Modal */}
        <AddRelationshipModal
          isOpen={isAddingUnit}
          userLovedOnes={availableLovedOnes}
          email={newUnitEmail}
          relationship={newUnitRel}
          isLoading={isAddingUnitLoading}
          onClose={() => {
            setIsAddingUnit(false);
            setNewUnitEmail('');
            setNewUnitRel('Partner');
          }}
          onEmailChange={setNewUnitEmail}
          onRelationshipChange={setNewUnitRel}
          onAdd={() => onAddRelationship(newUnitEmail, newUnitRel)}
          onRemove={onRemoveRelationship}
        />

        {/* Reaction Menu */}
        <ReactionMenu
          target={reactionMenuTarget}
          position={menuPosition}
          onReaction={handleReaction}
          onClose={handleCloseReactionMenu}
        />

        {/* Invite Link Modal (when clicking a pending unit in the tray) */}
        {inviteLinkModal.person && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white w-full max-w-md border-2 border-slate-900 p-6 shadow-[8px_8px_0px_rgba(15,23,42,1)] relative animate-slide-in-down">
              <button
                onClick={closeInviteLinkModal}
                className="absolute top-4 right-4 text-slate-400 hover:text-slate-900"
                aria-label="Close"
              >
                <X size={20} />
              </button>
              <h3 className="font-black text-slate-900 text-lg uppercase tracking-tight mb-2">
                Invite link – {inviteLinkModal.person.name}
              </h3>
              {inviteLinkModal.loading && (
                <div className="flex items-center gap-2 py-6 text-slate-500">
                  <Loader2 size={20} className="animate-spin" />
                  <span className="text-sm font-mono uppercase">Generating link…</span>
                </div>
              )}
              {inviteLinkModal.error && (
                <p className="text-sm text-red-600 py-4 font-mono">{inviteLinkModal.error}</p>
              )}
              {inviteLinkModal.url && !inviteLinkModal.loading && (
                <>
                  <p className="text-xs font-mono text-slate-500 mb-3">
                    Share this link with {inviteLinkModal.person.name} so they can join.
                  </p>
                  <div className="flex gap-2 mb-4">
                    <input
                      type="text"
                      value={inviteLinkModal.url}
                      readOnly
                      className="flex-1 bg-slate-50 border border-slate-300 p-2 text-xs font-mono text-slate-700 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={copyInviteLink}
                      className="flex-1 bg-white border-2 border-slate-900 hover:bg-slate-50 text-slate-900 text-xs font-bold uppercase tracking-widest py-3 flex items-center justify-center gap-2 transition-colors"
                    >
                      <Copy size={14} /> Copy
                    </button>
                    <button
                      onClick={shareInviteLink}
                      className="flex-1 bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold uppercase tracking-widest py-3 flex items-center justify-center gap-2 transition-colors"
                    >
                      <Share2 size={14} /> Share
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
};
