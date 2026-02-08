import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Send, Users, Zap, Lock, ChevronRight, ArrowRight, Wind, Heart, Trash2, Plus, Bug, AlertTriangle, ThumbsDown, Shield, MinusCircle, MapPin, Clock, Edit3, Camera } from 'lucide-react';
import { RoomHeader } from '../../../shared/ui/RoomHeader';
import { apiService } from '../../../shared/api/apiService';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import { useUiStore } from '../../../stores/ui.store';
import type { LoungeRoom, LoungeMessage } from '../../../shared/types/domain';

/** Optional conversation goals when starting a new Lounge session. Value is sent to backend; Kai uses it to tailor responses. */
const CONVERSATION_GOALS = [
  { value: '', label: 'No specific goal' },
  { value: 'resolve_a_conflict', label: 'Resolve a conflict' },
  { value: 'talk_about_feelings', label: 'Talk about feelings' },
  { value: 'ask_for_solution', label: 'Ask for a solution' },
  { value: 'vent_or_support', label: 'Vent or get support' },
  { value: 'plan_something', label: 'Plan something together' },
  { value: 'just_chat', label: 'Just chat' },
] as const;

interface Props {
  onExit: () => void;
}

export const LoungeScreen: React.FC<Props> = ({ onExit }) => {
  const { me: user, accessToken } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  const showToast = useUiStore((s) => s.showToast);
  const [rooms, setRooms] = useState<LoungeRoom[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [roomDetail, setRoomDetail] = useState<{
    owner_user_id?: string;
    members: { user_id: string; joined_at: string | null; display_name?: string | null }[];
    messages: LoungeMessage[];
  } | null>(null);
  const [publicInput, setPublicInput] = useState('');
  const [privateInput, setPrivateInput] = useState('');
  const [privateMessages, setPrivateMessages] = useState<LoungeMessage[]>([]);
  const [vetSuggestion, setVetSuggestion] = useState<{ draft: string; suggestion: string; revised_text?: string | null; horseman?: string | null } | null>(null);
  const [guidance, setGuidance] = useState<{
    guidance_type: string;
    text?: string | null;
    suggested_phrase?: string | null;
    debug_prompt?: string | null;
    debug_response?: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [invitePickerOpen, setInvitePickerOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [conversationGoal, setConversationGoal] = useState<string>('');
  const [removeConfirmOpen, setRemoveConfirmOpen] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [inviteSuggestion, setInviteSuggestion] = useState<{ user_id: string; display_name: string } | null>(null);
  const [activitySuggestions, setActivitySuggestions] = useState<Array<{ title: string; description?: string; recommendation_rationale?: string; estimated_minutes?: number; recommended_location?: string; recommended_invitee_name?: string; vibe_tags?: string[] }> | null>(null);
  const [activitySuggestionsRationale, setActivitySuggestionsRationale] = useState<string | null>(null);
  const [voucherSuggestions, setVoucherSuggestions] = useState<Array<{ title: string; description: string }> | null>(null);
  const [kaiTyping, setKaiTyping] = useState(false);
  const [kaiStreamingContent, setKaiStreamingContent] = useState<string | null>(null);
  const [kaiStreamingDisplayedLength, setKaiStreamingDisplayedLength] = useState(0);
  const [kaiPendingMessage, setKaiPendingMessage] = useState<LoungeMessage | null>(null);
  const [kaiDebugByMessageId, setKaiDebugByMessageId] = useState<Record<string, { prompt: string; response: string }>>({});
  const [debugModalMessageId, setDebugModalMessageId] = useState<string | null>(null);
  const [privateWindowOpen, setPrivateWindowOpen] = useState(false);
  const [guidanceAsPrivateMessage, setGuidanceAsPrivateMessage] = useState<LoungeMessage | null>(null);
  const [privateWindowTransformOrigin, setPrivateWindowTransformOrigin] = useState<{ x: number; y: number } | null>(null);
  const [privateWindowAnimateOpen, setPrivateWindowAnimateOpen] = useState(false);
  const [screenshotFiles, setScreenshotFiles] = useState<File[]>([]);
  const [analyzingScreenshots, setAnalyzingScreenshots] = useState(false);
  const [screenshotMessageAnalysis, setScreenshotMessageAnalysis] = useState<{
    extracted_thread: Array<{ sender_label: string; content: string }>;
    message_analysis: Array<{
      message_index: number;
      sender_label: string;
      content: string;
      suggested_revision?: string | null;
      guidance_type?: string | null;
      guidance_text?: string | null;
      suggested_phrase?: string | null;
    }>;
  } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const privateScrollRef = useRef<HTMLDivElement>(null);
  const lastMessageCountRef = useRef(0);
  const lastHadScreenshotAnalysisRef = useRef(false);
  const wasNearBottomRef = useRef(true);
  const roomWsRef = useRef<WebSocket | null>(null);
  const guidanceTriggerRectRef = useRef<{ x: number; y: number } | null>(null);
  const privatePanelRef = useRef<HTMLDivElement>(null);

  // Animate private window open from guidance position (or center)
  useEffect(() => {
    if (!privateWindowOpen) return;
    const id = requestAnimationFrame(() => {
      const panel = privatePanelRef.current;
      if (!panel) {
        setPrivateWindowAnimateOpen(true);
        return;
      }
      const rect = panel.getBoundingClientRect();
      const origin = guidanceTriggerRectRef.current;
      if (origin) {
        setPrivateWindowTransformOrigin({ x: origin.x - rect.left, y: origin.y - rect.top });
        guidanceTriggerRectRef.current = null;
      }
      setTimeout(() => setPrivateWindowAnimateOpen(true), 20);
    });
    return () => cancelAnimationFrame(id);
  }, [privateWindowOpen]);

  const showDebug = user?.preferences?.showDebug ?? (typeof localStorage !== 'undefined' ? localStorage.getItem('inside_show_debug') !== 'false' : true);
  const lovedOnes = relationships.length > 0 ? relationships : (user?.lovedOnes ?? []);

  const horsemanIcon = (horseman: string | null | undefined, size = 14, className = 'text-[#EA580C]') => {
    if (!horseman) return null;
    const s = horseman.toLowerCase();
    if (s === 'criticism') return <AlertTriangle size={size} className={className} aria-label="Criticism" />;
    if (s === 'contempt') return <ThumbsDown size={size} className={className} aria-label="Contempt" />;
    if (s === 'defensiveness') return <Shield size={size} className={className} aria-label="Defensiveness" />;
    if (s === 'stonewalling') return <MinusCircle size={size} className={className} aria-label="Stonewalling" />;
    return null;
  };

  const loadRooms = useCallback(async () => {
    try {
      const res = await apiService.listLoungeRooms();
      const list = (res.data as LoungeRoom[]) || [];
      setRooms(list);
    } catch (e) {
      console.warn('Lounge list rooms failed', e);
    }
  }, []);

  const loadRoomDetail = useCallback(async (roomId: string) => {
    try {
      const res = await apiService.getLoungeRoom(roomId);
      const data = res.data as {
        id: string;
        owner_user_id?: string;
        members: { user_id: string; joined_at: string | null; display_name?: string | null }[];
        messages: LoungeMessage[];
        guidance?: { guidance_type: string; text?: string | null; suggested_phrase?: string | null; debug_prompt?: string | null; debug_response?: string | null } | null;
      };
      const messages = data.messages || [];
      setRoomDetail((prev) => {
        // Don't overwrite with fewer messages (stale GET from poll/race) when still on this room
        if (prev && prev.messages.length > messages.length) return prev;
        return {
          owner_user_id: data.owner_user_id,
          members: data.members,
          messages,
        };
      });
      if (data.guidance) setGuidance(data.guidance);
      // Solo room: no guidance or vet UI; clear any stale guidance from a previous room/session
      if ((data.members?.length ?? 0) <= 1) {
        setGuidance(null);
        setVetSuggestion(null);
      }
    } catch (e) {
      console.warn('Lounge get room failed', e);
    }
  }, []);

  const loadPrivateMessages = useCallback(async (roomId: string) => {
    try {
      const res = await apiService.listLoungePrivateMessages(roomId);
      setPrivateMessages((res.data as { messages: LoungeMessage[] }).messages || []);
    } catch (e) {
      console.warn('Lounge private messages failed', e);
    }
  }, []);

  useEffect(() => {
    loadRooms();
  }, [loadRooms]);

  // Refetch room list and current room detail when app/tab gains focus so invitee sees new room and new messages
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      loadRooms();
      if (selectedRoomId) loadRoomDetail(selectedRoomId);
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, [loadRooms, loadRoomDetail, selectedRoomId]);

  useEffect(() => {
    setScreenshotMessageAnalysis(null);
  }, [selectedRoomId]);

  useEffect(() => {
    if (!selectedRoomId) return;
    loadRoomDetail(selectedRoomId);
    loadPrivateMessages(selectedRoomId);
    const roomId = selectedRoomId;
    // Use store token or apiService (localStorage) so WS connects even if store hasn't hydrated yet
    const token = accessToken ?? apiService.getAccessToken() ?? null;
    if (!token) return;
    const ws = apiService.connectLoungeRoomWebSocket(
      roomId,
      token,
      (msg) => {
        if (msg.type === 'lounge_room_update' && msg.room_id === roomId) {
          loadRoomDetail(roomId);
        }
        if (msg.type === 'lounge_guidance' && msg.room_id === roomId && msg.guidance) {
          setGuidance(msg.guidance);
        }
      },
      () => {},
      () => {}
    );
    roomWsRef.current = ws ?? null;
    // Poll room detail so messages from others appear even when WebSocket has no connections (e.g. cross-device, WS failed)
    const pollIntervalMs = 2000;
    const pollTimer = setInterval(() => {
      loadRoomDetail(roomId);
    }, pollIntervalMs);
    return () => {
      clearInterval(pollTimer);
      if (roomWsRef.current) {
        roomWsRef.current.close();
        roomWsRef.current = null;
      }
    };
  }, [selectedRoomId, loadRoomDetail, loadPrivateMessages, accessToken]);

  useEffect(() => {
    wasNearBottomRef.current = true;
    lastMessageCountRef.current = 0;
    lastHadScreenshotAnalysisRef.current = false;
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const threshold = 150;
      wasNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [selectedRoomId]);

  useEffect(() => {
    const messages = roomDetail?.messages ?? [];
    const messageCount = messages.length;
    const hadScreenshotAnalysis = !!screenshotMessageAnalysis && (screenshotMessageAnalysis.message_analysis?.length ?? 0) > 0;
    const contentGrew =
      messageCount > lastMessageCountRef.current ||
      (hadScreenshotAnalysis && !lastHadScreenshotAnalysisRef.current);
    const shouldFollow = kaiTyping || !!kaiStreamingContent;
    const scrollEl = scrollRef.current;
    const mayScroll = scrollEl && ((contentGrew && wasNearBottomRef.current) || shouldFollow);
    if (mayScroll) {
      scrollEl.scrollTop = scrollEl.scrollHeight;
    }
    lastMessageCountRef.current = messageCount;
    lastHadScreenshotAnalysisRef.current = hadScreenshotAnalysis;
  }, [roomDetail?.messages, kaiTyping, kaiStreamingContent, screenshotMessageAnalysis]);

  useEffect(() => {
    if (privateWindowOpen && privateScrollRef.current) {
      privateScrollRef.current.scrollTop = privateScrollRef.current.scrollHeight;
    }
  }, [privateWindowOpen, privateMessages]);

  // Simulate streaming: reveal Kai reply text progressively inside the list item. Message is already in list when kai_reply is received.
  useEffect(() => {
    if (kaiStreamingContent == null || kaiStreamingDisplayedLength >= kaiStreamingContent.length) {
      if (kaiStreamingContent != null) {
        setKaiStreamingContent(null);
        setKaiStreamingDisplayedLength(0);
        setKaiPendingMessage(null);
      } else {
        setKaiStreamingContent(null);
        setKaiStreamingDisplayedLength(0);
      }
      return;
    }
    const t = setTimeout(() => {
      setKaiStreamingDisplayedLength((n) => Math.min(n + 2, kaiStreamingContent.length));
    }, 25);
    return () => clearTimeout(t);
  }, [kaiStreamingContent, kaiStreamingDisplayedLength, kaiPendingMessage]);

  const createRoomWithGoal = async (goal?: string, e?: React.MouseEvent) => {
    e?.preventDefault?.();
    if (creating) return;
    if (!user?.id) {
      showToast('Please sign in to create a chat group');
      return;
    }
    setCreating(true);
    try {
      const res = await apiService.createLoungeRoom(null, goal || undefined);
      const data = res.data as { id?: string } | undefined;
      const roomId = data?.id;
      if (roomId) {
        setSelectedRoomId(roomId);
        loadRooms();
      } else {
        showToast('Chat group created — refresh the list');
        loadRooms();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Create chat group failed';
      showToast(message);
      console.warn('Create lounge room failed', err);
    } finally {
      setCreating(false);
    }
  };
  const handleCreateRoom = async (e?: React.MouseEvent) => {
    await createRoomWithGoal(conversationGoal || undefined, e);
  };

  const handleCreateRoomFromScreenshots = async (e?: React.MouseEvent) => {
    await createRoomWithGoal('analyze_screenshots', e);
  };

  const handleInvite = async (userId: string) => {
    if (!selectedRoomId) return;
    try {
      await apiService.inviteToLoungeRoom(selectedRoomId, userId);
      setInvitePickerOpen(false);
      loadRoomDetail(selectedRoomId);
    } catch (e) {
      console.warn('Invite to lounge failed', e);
    }
  };

  const handleRemoveChatGroup = async () => {
    if (!selectedRoomId || removing) return;
    setRemoving(true);
    try {
      await apiService.deleteLoungeRoom(selectedRoomId);
      setRemoveConfirmOpen(false);
      setSelectedRoomId(null);
      setRoomDetail(null);
      loadRooms();
      showToast('Chat group removed');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to remove chat group';
      showToast(message);
      console.warn('Delete lounge room failed', e);
    } finally {
      setRemoving(false);
    }
  };

  const handleAnalyzeScreenshots = async () => {
    if (!selectedRoomId || screenshotFiles.length === 0 || analyzingScreenshots) return;
    setAnalyzingScreenshots(true);
    setScreenshotMessageAnalysis(null);
    try {
      const res = await apiService.analyzeLoungeScreenshots(selectedRoomId, screenshotFiles);
      loadRoomDetail(selectedRoomId);
      setScreenshotFiles([]);
      if (res.data?.message_analysis?.length) {
        setScreenshotMessageAnalysis({
          extracted_thread: res.data.extracted_thread ?? [],
          message_analysis: res.data.message_analysis,
        });
      }
      showToast('Guidance posted to thread');
    } catch (e) {
      const err = e instanceof Error ? e.message : 'Analysis failed';
      showToast(err);
      console.warn('Analyze screenshots failed', e);
    } finally {
      setAnalyzingScreenshots(false);
    }
  };

  const sendPublicWithContent = useCallback(
    async (content: string, forceSend: boolean, optimisticId?: string) => {
      if (!selectedRoomId) return;
      const removeOptimistic = () => {
        if (!optimisticId) return;
        setRoomDetail((prev) => {
          if (!prev) return prev;
          const last = prev.messages[prev.messages.length - 1];
          if (last?.id === optimisticId) {
            return { ...prev, messages: prev.messages.slice(0, -1) };
          }
          return prev;
        });
      };
      setLoading(true);
      try {
        const res = await apiService.sendLoungeMessage(selectedRoomId, content, forceSend, showDebug);
        const data = res.data as {
          vet_ok?: boolean;
          suggestion?: string | null;
          revised_text?: string | null;
          horseman?: string | null;
          message?: LoungeMessage;
          guidance?: { guidance_type: string; text?: string | null; suggested_phrase?: string | null; debug_prompt?: string | null; debug_response?: string | null } | null;
          kai_reply?: { content: string; message?: LoungeMessage; prompt?: string | null; response?: string | null } | null;
          invite_suggestion?: { user_id: string; display_name: string } | null;
          intention_detected?: { suggest_activities: boolean; activity_query: string | null; suggest_vouchers: boolean };
          activity_suggestions?: Array<{ title: string; description?: string; recommendation_rationale?: string; estimated_minutes?: number; recommended_location?: string; recommended_invitee_name?: string; vibe_tags?: string[] }> | null;
          activity_suggestions_rationale?: string | null;
          voucher_suggestions?: Array<{ title: string; description: string }> | null;
        };
        if (data.vet_ok === false && data.suggestion && !forceSend) {
          setVetSuggestion({
            draft: content,
            suggestion: data.suggestion,
            revised_text: data.revised_text ?? null,
            horseman: data.horseman ?? null,
          });
          setPublicInput(content);
          removeOptimistic();
          setKaiTyping(false);
        } else {
          setVetSuggestion(null);
          setGuidance(null); // Clear guidance when user sends (adopts the conversation)
          setPublicInput('');
          if (data.guidance) setGuidance(data.guidance);
          if (data.invite_suggestion) setInviteSuggestion(data.invite_suggestion);
          else setInviteSuggestion(null);
          setActivitySuggestions(data.activity_suggestions ?? null);
          setActivitySuggestionsRationale(data.activity_suggestions_rationale ?? null);
          setVoucherSuggestions(data.voucher_suggestions ?? null);
          // Remove optimistic message (if still present), then add server message and Kai reply only if not already in list (poll may have already loaded them).
          setRoomDetail((prev) => {
            if (!prev) return prev;
            let next = prev.messages.filter((m) => m.id !== optimisticId);
            if (data.message && !next.some((m) => m.id === data.message!.id)) {
              next = [...next, data.message];
            }
            if (data.kai_reply?.content && data.kai_reply?.message && !next.some((m) => m.id === data.kai_reply!.message!.id)) {
              next = [...next, data.kai_reply.message];
            }
            return prev.messages === next ? prev : { ...prev, messages: next };
          });
          if (data.kai_reply?.content && data.kai_reply?.message) {
            setKaiTyping(false);
            setKaiStreamingContent(data.kai_reply.content);
            setKaiStreamingDisplayedLength(0);
            setKaiPendingMessage(data.kai_reply.message);
            if (data.kai_reply.message.id && (data.kai_reply.prompt != null || data.kai_reply.response != null)) {
              setKaiDebugByMessageId((prev) => ({
                ...prev,
                [data.kai_reply!.message!.id]: {
                  prompt: data.kai_reply!.prompt ?? '',
                  response: data.kai_reply!.response ?? '',
                },
              }));
            }
          } else {
            setKaiTyping(false);
          }
        }
      } catch (e) {
        console.warn('Send lounge message failed', e);
        showToast('Failed to send message');
        setPublicInput(content);
        removeOptimistic();
        setKaiTyping(false);
      } finally {
        setLoading(false);
      }
    },
    [selectedRoomId, showToast, showDebug]
  );

  const handleSendPublic = async (e?: React.MouseEvent, forceSend = false) => {
    e?.preventDefault?.();
    // If rephrase suggestion is showing and user clicks Send again, treat as "send anyway": force-send the draft and dismiss the suggestion.
    const sendingAnyway = Boolean(vetSuggestion);
    if (sendingAnyway) {
      forceSend = true;
      setVetSuggestion(null);
    }
    const content = (forceSend && vetSuggestion?.draft) ? vetSuggestion.draft : publicInput.trim();
    const contentToSend = sendingAnyway ? (vetSuggestion?.draft ?? publicInput.trim()) : content;
    if (!selectedRoomId || !contentToSend.trim() || !user?.id) return;
    // Clear input and block double-submit immediately so the text box is cleared and Enter/click don't fire again
    setPublicInput('');
    setLoading(true);
    setActivitySuggestions(null);
    setActivitySuggestionsRationale(null);
    // Show user message immediately in the chat stream
    const optimisticId = `temp-${Date.now()}`;
    const optimisticMessage: LoungeMessage = {
      id: optimisticId,
      room_id: selectedRoomId,
      sender_user_id: user.id,
      sender_name: user.name ?? user.displayName ?? 'You',
      content: contentToSend,
      visibility: 'public',
      sequence: (roomDetail?.messages?.length ?? 0) + 1,
      created_at: new Date().toISOString(),
    };
    setRoomDetail((prev) => {
      if (!prev) return prev;
      return { ...prev, messages: [...prev.messages, optimisticMessage] };
    });
    // Show "typing..." only when Kai will reply in the thread (solo room). In multi-person rooms Kai only vets/generates guidance for others—no chat message.
    const soloRoom = (roomDetail?.members?.length ?? 0) <= 1;
    if (soloRoom) setKaiTyping(true);
    await sendPublicWithContent(contentToSend, forceSend, optimisticId);
  };

  const handleSendPrivate = async () => {
    if (!selectedRoomId || !privateInput.trim() || loading) return;
    const content = privateInput.trim();
    setPrivateInput('');
    setLoading(true);
    try {
      const res = await apiService.sendLoungePrivateMessage(selectedRoomId, content);
      const data = res.data as {
        user_message: LoungeMessage;
        kai_reply: { content: string; message?: LoungeMessage; prompt?: string | null; response?: string | null } | null;
      };
      // Merge response into list immediately so UI shows new messages; avoid refetch race where an older GET overwrites state.
      if (data?.user_message) {
        const kaiMsg: LoungeMessage | null =
          data.kai_reply?.content && data.kai_reply?.message
            ? { ...data.kai_reply.message, content: data.kai_reply.content }
            : data.kai_reply?.content
              ? {
                  id: `kai-temp-${Date.now()}`,
                  room_id: selectedRoomId,
                  sender_user_id: null,
                  sender_name: 'Kai',
                  content: data.kai_reply.content,
                  visibility: 'private_to_kai',
                  sequence: 0,
                  created_at: new Date().toISOString(),
                }
              : null;
        setPrivateMessages((prev) =>
          [...prev, data.user_message, ...(kaiMsg ? [kaiMsg] : [])]
        );
        if (data.kai_reply?.message?.id && (data.kai_reply.prompt != null || data.kai_reply.response != null)) {
          setKaiDebugByMessageId((prev) => ({
            ...prev,
            [data.kai_reply!.message!.id]: {
              prompt: data.kai_reply!.prompt ?? '',
              response: data.kai_reply!.response ?? '',
            },
          }));
        }
      }
      // Refetch to get canonical list (real IDs, order); await so a fast second send doesn't overwrite with stale GET.
      await loadPrivateMessages(selectedRoomId);
    } catch (e) {
      console.warn('Send private failed', e);
      setPrivateInput(content);
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  // ---- Room list (no room selected) ----
  if (!selectedRoomId) {
    return (
      <div
        className="flex flex-col h-screen relative font-sans text-[#1A1A1A] antialiased"
        style={{
          backgroundColor: '#ffffff',
          backgroundImage: 'linear-gradient(to right, rgba(59, 130, 246, 0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(59, 130, 246, 0.08) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      >
        <RoomHeader
          moduleTitle="MODULE: CONNECT"
          title="Living Room"
          subtitle={{ text: 'GROUP CHAT', colorClass: 'text-[#3b82f6]' }}
          titleClassName="text-4xl font-black uppercase tracking-tight leading-none text-slate-900"
          onClose={onExit}
        />
        <div className="flex-1 min-h-0 overflow-y-auto p-6 w-full max-w-4xl mx-auto flex flex-col gap-6">
          <div className="flex items-center gap-2 mb-2 opacity-60">
            <span className="text-[11px] uppercase tracking-[0.15em] font-mono text-slate-500">Active Sessions</span>
          </div>
          {rooms.map((r, index) => {
            const label = r.title || `Chat group ${r.id.slice(0, 8)}`;
            const roomInitial = (label.charAt(0) || '?').toUpperCase();
            const memberList = r.members ?? [];
            const initials = memberList.length > 0
              ? memberList.map((m) => ((m.display_name ?? '').trim().charAt(0) || (m.user_id ?? '').charAt(0) || '?').toUpperCase())
              : [roomInitial];
            const isFirst = index === 0;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelectedRoomId(r.id)}
                className={`group relative w-full text-left overflow-visible transition-all cursor-pointer ${
                  isFirst
                    ? 'bg-white border-2 border-slate-900 shadow-[4px_4px_0px_0px_rgba(15,23,42,0.1)] active:translate-y-[2px] active:translate-x-[2px] active:shadow-none'
                    : 'bg-white border-2 border-slate-200 hover:border-slate-900'
                }`}
              >
                <div
                  className={`flex justify-between items-stretch border-b-2 ${
                    isFirst ? 'border-slate-900 bg-slate-50' : 'border-slate-200 group-hover:border-slate-900 bg-slate-50/50'
                  }`}
                >
                  <div className="px-5 py-3 flex-1">
                    <h3
                      className={`text-lg font-bold uppercase tracking-wide leading-tight ${
                        isFirst ? '' : 'text-slate-700 group-hover:text-slate-900'
                      }`}
                    >
                      {label}
                    </h3>
                  </div>
                  <div
                    className={`text-[10px] font-mono font-bold px-3 py-3 uppercase tracking-wider flex items-center ${
                      isFirst
                        ? 'bg-slate-900 text-white'
                        : 'bg-slate-100 text-slate-500 group-hover:bg-slate-900 group-hover:text-white border-l-2 border-slate-200 group-hover:border-slate-900'
                    }`}
                  >
                    Active
                  </div>
                </div>
                <div className="p-5 pt-4 pb-6">
                  <div className="flex justify-between items-center gap-2 mb-6">
                    <p className="text-xs text-slate-600 font-mono line-clamp-2 flex-1 min-w-0">
                      {r.topic && r.topic.trim() ? r.topic.trim() : '—'}
                    </p>
                    <ArrowRight className="text-slate-300 group-hover:text-[#3b82f6] transition-colors shrink-0" size={20} />
                  </div>
                  <div className="flex items-center justify-between min-h-8">
                    <div className="flex -space-x-0 gap-1 overflow-visible">
                      {initials.slice(0, 4).map((initial, i) => (
                        <div
                          key={i}
                          className="inline-block h-8 w-8 rounded-none border border-slate-200 bg-slate-200 flex items-center justify-center font-mono font-bold text-xs text-slate-600 shrink-0"
                        >
                          {initial}
                        </div>
                      ))}
                    </div>
                    <div className="text-[10px] font-mono text-green-600 font-bold flex items-center gap-2 border border-green-200 bg-green-50 px-2 py-1 shrink-0">
                      <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                      Active
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
        <div className="sticky bottom-0 z-40 p-6 bg-gradient-to-t from-white via-white to-transparent pt-12 shrink-0">
          <div className="mb-4">
            <label htmlFor="lounge-goal" className="block text-[10px] font-mono uppercase tracking-widest text-slate-500 mb-1.5">
              Goal of this conversation (optional)
            </label>
            <select
              id="lounge-goal"
              value={conversationGoal}
              onChange={(e) => setConversationGoal(e.target.value)}
              className="w-full border-2 border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-900 focus:border-slate-900 focus:outline-none rounded-none"
            >
              {CONVERSATION_GOALS.map((g) => (
                <option key={g.value || 'none'} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={(e) => handleCreateRoom(e)}
              disabled={creating}
              className="flex-1 group relative bg-transparent overflow-hidden border-2 border-slate-900 py-2 px-3 transition-all hover:bg-slate-900 disabled:opacity-50 disabled:hover:bg-transparent"
            >
              <div className="absolute top-0 left-0 w-2 h-2 bg-slate-900" />
              <div className="absolute top-0 right-0 w-2 h-2 bg-slate-900" />
              <div className="absolute bottom-0 left-0 w-2 h-2 bg-slate-900" />
              <div className="absolute bottom-0 right-0 w-2 h-2 bg-slate-900" />
              <div className="flex items-center justify-center gap-1.5 relative z-10">
                <Plus size={16} className="text-slate-900 group-hover:text-white transition-colors shrink-0" />
                <span className="font-bold text-xs uppercase tracking-[0.1em] text-slate-900 group-hover:text-white transition-colors">
                  {creating ? 'Creating...' : 'Initiate New Session'}
                </span>
              </div>
            </button>
            <button
              type="button"
              onClick={(e) => handleCreateRoomFromScreenshots(e)}
              disabled={creating}
              className="flex-1 group relative bg-slate-900 overflow-hidden border-2 border-slate-900 py-2 px-3 transition-all hover:bg-slate-800 disabled:opacity-50 disabled:hover:bg-slate-900"
            >
              <div className="absolute top-0 left-0 w-2 h-2 bg-white" />
              <div className="absolute top-0 right-0 w-2 h-2 bg-white" />
              <div className="absolute bottom-0 left-0 w-2 h-2 bg-white" />
              <div className="absolute bottom-0 right-0 w-2 h-2 bg-white" />
              <div className="flex items-center justify-center gap-1.5 relative z-10">
                <Camera size={16} className="text-white transition-colors shrink-0" />
                <span className="font-bold text-xs uppercase tracking-[0.1em] text-white transition-colors">
                  {creating ? 'Creating...' : 'Start from Chat Screenshots'}
                </span>
              </div>
            </button>
          </div>
          <p className="text-center mt-4 text-[10px] font-mono text-slate-400 uppercase tracking-widest">System v2.4.0 • Secure Connection</p>
        </div>
      </div>
    );
  }

  // ---- Room view ----
  const messages = roomDetail?.messages ?? [];
  const members = roomDetail?.members ?? [];
  const hasScreenshotAnalysis = screenshotMessageAnalysis && screenshotMessageAnalysis.message_analysis.length > 0;
  const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null;
  const kaiMessageAfterAnalysis = hasScreenshotAnalysis && lastMsg?.sender_user_id === null ? lastMsg : null;
  const messagesToShow = kaiMessageAfterAnalysis ? messages.slice(0, -1) : messages;

  return (
    <div
      className="flex flex-col h-screen relative font-sans text-[#1A1A1A] antialiased"
      style={{
        backgroundColor: '#f7f7f7',
        backgroundImage: 'linear-gradient(to right, rgba(15, 23, 42, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(15, 23, 42, 0.05) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }}
    >
      <RoomHeader
        moduleTitle="MODULE: CONNECT"
        title="Living Room"
        subtitle={{ text: 'COACHING SESSION ACTIVE', colorClass: 'text-indigo-600' }}
        onClose={onExit}
        headerRight={
          <div className="flex items-center gap-2">
            {roomDetail?.owner_user_id === user?.id && (
              <button
                type="button"
                onClick={() => setRemoveConfirmOpen(true)}
                className="flex items-center gap-1 px-2 py-1 border border-red-600 text-red-600 text-[10px] font-bold uppercase hover:bg-red-50"
                title="Remove chat group"
              >
                <Trash2 size={12} /> Remove
              </button>
            )}
            <button
              type="button"
              onClick={() => setInvitePickerOpen(true)}
              className="flex items-center gap-1 px-2 py-1 border border-[#1A1A1A] text-[10px] font-bold uppercase"
            >
              <Users size={12} /> Invite
            </button>
          </div>
        }
      />

      {removeConfirmOpen && (
        <div className="absolute inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white border-2 border-[#1A1A1A] p-4 w-full max-w-sm">
            <p className="text-xs font-mono font-bold uppercase mb-3">Remove this chat group?</p>
            <p className="text-sm text-slate-600 mb-4">This cannot be undone. All messages and participants will be removed.</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setRemoveConfirmOpen(false)}
                disabled={removing}
                className="flex-1 py-2 border-2 border-[#1A1A1A] bg-white font-bold uppercase text-sm disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRemoveChatGroup}
                disabled={removing}
                className="flex-1 py-2 border-2 border-red-600 bg-red-50 text-red-600 font-bold uppercase text-sm disabled:opacity-50"
              >
                {removing ? 'Removing...' : 'Remove'}
              </button>
            </div>
          </div>
        </div>
      )}

      {invitePickerOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="relative w-full max-w-sm bg-white border-4 border-[#1A1A1A] shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] p-0 overflow-hidden">
            <div
              className="absolute inset-0 opacity-30 pointer-events-none z-0"
              style={{
                backgroundImage: 'radial-gradient(#cbd5e1 1px, transparent 1px)',
                backgroundSize: '20px 20px',
              }}
            />
            <div className="relative z-10 flex flex-col">
              <div className="bg-white p-6 pb-4 border-b-2 border-[#1A1A1A]">
                <h2 className="font-mono text-xl font-bold uppercase tracking-wide text-[#1A1A1A]">
                  Invite Loved One
                </h2>
                <div className="h-1 w-12 bg-[#1A1A1A] mt-2" />
              </div>
              <div className="p-6 flex flex-col gap-4 bg-slate-50 max-h-60 overflow-y-auto">
                {(() => {
                  const memberIds = new Set((roomDetail?.members ?? []).map((m) => m.user_id));
                  return lovedOnes.map((lo) => {
                    const isAlreadyInRoom = memberIds.has(lo.id);
                    return (
                      <button
                        key={lo.id}
                        type="button"
                        onClick={() => !isAlreadyInRoom && handleInvite(lo.id)}
                        disabled={isAlreadyInRoom}
                        className="group relative w-full text-left focus:outline-none disabled:pointer-events-none"
                      >
                        <div
                          className={`absolute inset-0 translate-x-1 translate-y-1 transition-transform ${
                            isAlreadyInRoom ? 'bg-emerald-600' : 'bg-[#1A1A1A] group-hover:translate-x-2 group-hover:translate-y-2'
                          }`}
                        />
                        <div
                          className={`relative border-2 p-4 flex justify-between items-center transition-transform ${
                            isAlreadyInRoom
                              ? 'bg-emerald-50 border-emerald-600 text-emerald-800'
                              : 'bg-white border-[#1A1A1A] active:translate-x-1 active:translate-y-1'
                          }`}
                        >
                          <span
                            className={`font-bold text-lg ${
                              isAlreadyInRoom ? 'text-emerald-800' : 'text-[#1A1A1A] group-hover:underline decoration-2 underline-offset-4'
                            }`}
                          >
                            {lo.name}
                          </span>
                          <span
                            className={`text-xs uppercase tracking-wider font-medium px-2 py-1 rounded-sm border ${
                              isAlreadyInRoom
                                ? 'text-emerald-700 bg-emerald-100 border-emerald-300'
                                : 'text-slate-500 bg-slate-100 border-slate-200'
                            }`}
                          >
                            {isAlreadyInRoom ? 'In room' : lo.relationship}
                          </span>
                        </div>
                      </button>
                    );
                  });
                })()}
                <button
                  type="button"
                  onClick={() => setInvitePickerOpen(false)}
                  className="flex items-center gap-2 text-slate-400 hover:text-[#1A1A1A] mt-2 px-1 transition-colors group"
                >
                  <div className="border border-dashed border-slate-400 group-hover:border-[#1A1A1A] h-6 w-6 flex items-center justify-center">
                    <Plus size={12} />
                  </div>
                  <span className="text-xs font-bold uppercase tracking-widest">Add Contact</span>
                </button>
              </div>
              <div className="p-6 pt-2 bg-slate-50">
                <button
                  type="button"
                  onClick={() => setInvitePickerOpen(false)}
                  className="w-full bg-white text-[#1A1A1A] font-black uppercase tracking-widest py-4 border-4 border-[#1A1A1A] hover:bg-[#1A1A1A] hover:text-white transition-colors shadow-[4px_4px_0px_0px_rgba(0,0,0,0.1)] active:shadow-none active:translate-x-0.5 active:translate-y-0.5"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="absolute top-0 left-0 w-2 h-2 border-t-2 border-l-2 border-[#1A1A1A] z-20 pointer-events-none" />
            <div className="absolute top-0 right-0 w-2 h-2 border-t-2 border-r-2 border-[#1A1A1A] z-20 pointer-events-none" />
            <div className="absolute bottom-0 left-0 w-2 h-2 border-b-2 border-l-2 border-[#1A1A1A] z-20 pointer-events-none" />
            <div className="absolute bottom-0 right-0 w-2 h-2 border-b-2 border-r-2 border-[#1A1A1A] z-20 pointer-events-none" />
          </div>
        </div>
      )}

      {debugModalMessageId && (
        <div className="absolute inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white border-2 border-[#1A1A1A] p-4 w-full max-w-lg max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-mono font-bold uppercase text-slate-600">
                {debugModalMessageId === 'guidance' ? 'Kai guidance LLM debug' : 'Kai LLM debug'}
              </p>
              <button
                type="button"
                onClick={() => setDebugModalMessageId(null)}
                className="p-1 rounded hover:bg-slate-100"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            {(() => {
              const debugInfo =
                debugModalMessageId === 'guidance'
                  ? guidance?.debug_prompt != null || guidance?.debug_response != null
                    ? { prompt: guidance.debug_prompt ?? '', response: guidance.debug_response ?? '' }
                    : null
                  : kaiDebugByMessageId[debugModalMessageId];
              return debugInfo ? (
                <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
                  <div>
                    <p className="text-[10px] font-mono font-bold uppercase text-slate-500 mb-1">Prompt</p>
                    <pre className="text-xs font-mono bg-slate-50 border border-slate-200 p-3 rounded overflow-x-auto whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                      {debugInfo.prompt}
                    </pre>
                  </div>
                  <div>
                    <p className="text-[10px] font-mono font-bold uppercase text-slate-500 mb-1">Response</p>
                    <pre className="text-xs font-mono bg-slate-50 border border-slate-200 p-3 rounded overflow-x-auto whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                      {debugInfo.response}
                    </pre>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">Debug info not available.</p>
              );
            })()}
            <button
              type="button"
              onClick={() => setDebugModalMessageId(null)}
              className="mt-4 w-full py-2 border-2 border-[#1A1A1A] font-bold uppercase text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {privateWindowOpen && selectedRoomId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 transition-[background-color] duration-200 ease-out"
          style={{ backgroundColor: privateWindowAnimateOpen ? 'rgba(0,0,0,0.4)' : 'rgba(0,0,0,0)' }}
        >
          <div
            ref={privatePanelRef}
            className="bg-white border-2 border-[#1A1A1A] shadow-xl w-full max-w-sm max-h-[70vh] flex flex-col transition-all duration-200 ease-out"
            style={{
              transformOrigin: privateWindowTransformOrigin ? `${privateWindowTransformOrigin.x}px ${privateWindowTransformOrigin.y}px` : 'center',
              transform: privateWindowAnimateOpen ? 'scale(1)' : 'scale(0.85)',
              opacity: privateWindowAnimateOpen ? 1 : 0,
            }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b-2 border-[#1A1A1A] shrink-0">
              <p className="text-xs font-mono font-bold uppercase text-slate-700">Private with Kai</p>
              <button
                type="button"
                onClick={() => {
                  setPrivateWindowOpen(false);
                  setPrivateWindowAnimateOpen(false);
                  setPrivateWindowTransformOrigin(null);
                  setGuidanceAsPrivateMessage(null);
                }}
                className="p-1 rounded hover:bg-slate-100"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>
            <div
              ref={privateScrollRef}
              className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3"
              style={{
                backgroundImage: 'radial-gradient(rgba(15, 23, 42, 0.08) 1px, transparent 1px)',
                backgroundSize: '8px 8px',
              }}
            >
              {(vetSuggestion || (guidance?.guidance_type && !guidanceAsPrivateMessage)) && (
                <div className="space-y-2 mb-3">
                  <p className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest">Kai&apos;s guidance</p>
                  {vetSuggestion && (
                    <div className="flex gap-2 items-start p-2 bg-orange-500/5 border border-orange-500/40">
                      {horsemanIcon(vetSuggestion.horseman, 12, 'text-[#EA580C] shrink-0 mt-0.5')}
                      <div className="min-w-0 flex-1">
                        <span className="text-[9px] font-mono font-bold uppercase text-[#EA580C]">Rephrase suggestion</span>
                        <p className="text-xs text-[#EA580C] mt-1">{vetSuggestion.suggestion}</p>
                        <button
                          type="button"
                          onClick={() => {
                            setPublicInput((vetSuggestion.revised_text?.trim()) ? vetSuggestion.revised_text!.trim() : vetSuggestion.suggestion);
                            setVetSuggestion(null);
                            setPrivateWindowOpen(false);
                            setPrivateWindowAnimateOpen(false);
                            setPrivateWindowTransformOrigin(null);
                            setGuidanceAsPrivateMessage(null);
                          }}
                          className="mt-1.5 text-[9px] font-mono font-bold uppercase text-[#EA580C] hover:underline"
                        >
                          Use revised text in chat group →
                        </button>
                      </div>
                    </div>
                  )}
                  {guidance?.guidance_type && (
                    (() => {
                      const t = guidance.guidance_type;
                      const isRephrase = t === 'rephrase_that';
                      const isAnalysis = t === 'analysis';
                      const borderBg = isRephrase ? 'bg-emerald-500/5 border-emerald-500/40' : isAnalysis ? 'bg-blue-500/5 border-blue-500/40' : 'bg-emerald-500/5 border-emerald-500/40';
                      const textColor = isRephrase ? 'text-[#059669]' : isAnalysis ? 'text-[#2563EB]' : 'text-[#059669]';
                      const label = isRephrase ? 'Rephrase' : isAnalysis ? 'Analysis' : 'Topic guidance';
                      const hasDebug = guidance.debug_prompt != null || guidance.debug_response != null;
                      return (
                        <div className={`flex gap-2 items-start p-2 border ${borderBg}`}>
                          <Zap size={12} className={`shrink-0 mt-0.5 ${textColor}`} />
                          <div className="min-w-0 flex-1">
                            <span className={`text-[9px] font-mono font-bold uppercase ${textColor}`}>{label}</span>
                            <p className={`text-xs mt-1 ${textColor}`}>{guidance.text ?? guidance.guidance_type.replace(/_/g, ' ')}</p>
                          </div>
                          {isRephrase && (guidance.suggested_phrase ?? '').trim() && (
                            <Edit3 size={12} className={`shrink-0 mt-0.5 ${textColor}`} aria-label="Click to use suggested phrase" />
                          )}
                          {hasDebug && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setDebugModalMessageId('guidance'); }}
                              className="shrink-0 p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
                              aria-label="Show LLM debug"
                            >
                              <Bug size={12} />
                            </button>
                          )}
                        </div>
                      );
                    })()
                  )}
                </div>
              )}
              {(() => {
                const privateStreamMessages = (guidanceAsPrivateMessage ? [guidanceAsPrivateMessage] : []).concat(privateMessages);
                return privateStreamMessages.length === 0 && !vetSuggestion ? (
                  <p className="text-xs font-mono text-slate-400 text-center py-4">
                    No messages yet. Share your thoughts below.
                    <span className="block mt-2 text-[10px] text-slate-500">You can tell Kai your preferences or give feedback—Kai will remember.</span>
                  </p>
                ) : privateStreamMessages.length > 0 ? (
                  privateStreamMessages.map((m) => {
                  const isYou = m.sender_user_id === user?.id;
                  const isKai = m.sender_user_id === null;
                  return (
                    <div
                      key={m.id}
                      className={`flex gap-2 ${isYou ? 'flex-row-reverse' : ''}`}
                    >
                      <div
                        className={`w-6 h-6 shrink-0 flex items-center justify-center font-bold text-[10px] ${
                          isKai ? 'bg-[#0D9488] text-white' : 'bg-[#1A1A1A] text-white'
                        }`}
                      >
                        {isYou ? (user?.name?.charAt(0) ?? 'U') : 'K'}
                      </div>
                      <div className={`max-w-[85%] ${isYou ? 'text-right' : ''}`}>
                        <div className="flex items-start justify-between gap-1">
                          <div
                            className={`p-2 shadow-sm flex-1 min-w-0 ${
                              isKai
                                ? 'bg-[#F0FDFA] border border-[#0D9488]'
                                : 'bg-white border-2 border-[#1A1A1A]'
                            }`}
                          >
                            <p className={`text-xs ${isKai ? 'text-[#0f766e]' : ''}`}>{m.content}</p>
                          </div>
                          {isKai && (kaiDebugByMessageId[m.id] != null) && (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); setDebugModalMessageId(m.id); }}
                              className="shrink-0 p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
                              aria-label="Show LLM debug"
                            >
                              <Bug size={12} />
                            </button>
                          )}
                        </div>
                        <span className="text-[8px] font-mono text-slate-400 uppercase block mt-0.5">
                          {isYou ? 'You' : 'Kai'}
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : null;
              })()}
            </div>
            <div className="p-3 border-t-2 border-[#1A1A1A] shrink-0 flex gap-0">
              <input
                type="text"
                value={privateInput}
                onChange={(e) => setPrivateInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSendPrivate();
                  }
                }}
                placeholder="Share your thoughts or tell Kai your preferences…"
                className="flex-1 border-2 border-[#1A1A1A] bg-white px-3 py-2 font-mono text-[10px] uppercase placeholder:text-slate-400/80"
                disabled={loading}
              />
              <button
                type="button"
                onClick={handleSendPrivate}
                disabled={!privateInput.trim() || loading}
                className="w-12 bg-[#1A1A1A] text-white flex items-center justify-center disabled:opacity-50"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="px-4 py-2 bg-white border-b-2 border-[#1A1A1A] shrink-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest">In this chat group</p>
            {members.length === 0 ? (
              <span className="text-[10px] font-mono text-slate-400">Just you</span>
            ) : null}
            {members.map((m) => {
              const isYou = m.user_id === user?.id;
              const name = isYou ? 'You' : (m.display_name ?? 'Member');
              const initial = isYou ? (user?.name?.charAt(0) ?? 'U') : (m.display_name?.charAt(0) ?? '?');
              return (
                <span
                  key={m.user_id}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 border-2 font-mono text-[10px] uppercase ${
                    isYou ? 'border-[#3B82F6] bg-[#EFF6FF] text-[#1A1A1A]' : 'border-[#1A1A1A] bg-white text-[#1A1A1A]'
                  }`}
                >
                  <span className="w-5 h-5 rounded-full bg-[#1A1A1A] text-white flex items-center justify-center font-bold text-[9px] shrink-0">
                    {initial}
                  </span>
                  {name}
                </span>
              );
            })}
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 border-2 border-[#0D9488]/50 bg-[#F0FDFA] font-mono text-[10px] uppercase text-[#0D9488]">
              <span className="w-5 h-5 rounded-full bg-[#0D9488]/30 text-[#0D9488] flex items-center justify-center font-bold text-[9px] shrink-0">
                K
              </span>
              Kai
            </span>
          </div>
        </div>

        {rooms.find((r) => r.id === selectedRoomId)?.conversation_goal === 'analyze_screenshots' && !screenshotMessageAnalysis && (
          <div className="px-4 py-3 bg-slate-50 border-b-2 border-slate-200 shrink-0">
            <p className="text-[9px] font-mono font-bold text-slate-600 uppercase tracking-widest mb-2">Analyze screenshots</p>
            <p className="text-xs text-slate-600 mb-2">Upload one or more screenshots of a chat. Kai will share its understanding and ask you to confirm or add context. Reply in the thread to get analysis and suggested next steps.</p>
            <div className="flex flex-wrap items-center gap-2">
              <label className="inline-flex items-center gap-1.5 px-3 py-2 border-2 border-[#1A1A1A] bg-white font-mono text-[10px] font-bold uppercase cursor-pointer hover:bg-slate-50">
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  className="sr-only"
                  onChange={(e) => setScreenshotFiles(Array.from(e.target.files ?? []))}
                />
                Choose images
              </label>
              {screenshotFiles.length > 0 && (
                <span className="text-[10px] font-mono text-slate-600">
                  {screenshotFiles.length} file{screenshotFiles.length !== 1 ? 's' : ''} selected
                </span>
              )}
              <button
                type="button"
                onClick={handleAnalyzeScreenshots}
                disabled={screenshotFiles.length === 0 || analyzingScreenshots}
                className="px-3 py-2 bg-[#1A1A1A] text-white font-mono text-[10px] font-bold uppercase disabled:opacity-50 hover:bg-slate-800"
              >
                {analyzingScreenshots ? 'Analyzing…' : 'Get guidance'}
              </button>
            </div>
          </div>
        )}

        {inviteSuggestion && (
          <div className="px-4 py-2 bg-emerald-50 border-b border-emerald-200 shrink-0 flex flex-wrap items-center justify-between gap-2">
            <span className="text-[10px] font-mono text-emerald-800">
              Kai suggests inviting <strong>{inviteSuggestion.display_name}</strong> to this chat group.
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  handleInvite(inviteSuggestion.user_id);
                  setInviteSuggestion(null);
                  loadRoomDetail(selectedRoomId!);
                  showToast(`${inviteSuggestion.display_name} invited`);
                }}
                className="px-3 py-1.5 bg-emerald-600 text-white text-[10px] font-bold uppercase"
              >
                Invite
              </button>
              <button
                type="button"
                onClick={() => setInviteSuggestion(null)}
                className="px-3 py-1.5 border border-emerald-300 text-emerald-700 text-[10px] font-bold uppercase"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0"
          style={{
            backgroundImage: 'radial-gradient(rgba(15, 23, 42, 0.2) 1px, transparent 1px)',
            backgroundSize: '10px 10px',
          }}
        >
          {messagesToShow.map((m) => {
            const isYou = m.sender_user_id === user.id;
            const isKai = m.sender_user_id === null;
            const isStreamingThis = isKai && kaiPendingMessage?.id === m.id && kaiStreamingContent != null;
            const displayContent = isStreamingThis
              ? kaiStreamingContent!.slice(0, kaiStreamingDisplayedLength)
              : m.content;
            return (
              <div
                key={m.id}
                className={`flex gap-3 ${isYou ? 'flex-row-reverse' : ''}`}
              >
                <div
                  className={`w-8 h-8 shrink-0 flex items-center justify-center font-bold text-xs ${
                    isKai ? 'bg-[#0D9488] text-white' : 'bg-[#1A1A1A] text-white'
                  }`}
                >
                  {isYou ? (user.name?.charAt(0) ?? 'U') : (m.sender_name?.charAt(0) ?? '?')}
                </div>
                <div className={`max-w-[85%] ${isYou ? 'text-right' : ''}`}>
                  <div
                    className={`p-3 shadow-[4px_4px_0px_0px_rgba(15,23,42,0.2)] ${
                      isKai
                        ? 'bg-[#F0FDFA] border-2 border-[#0D9488]'
                        : 'bg-white border-2 border-[#1A1A1A]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className={`text-sm flex-1 min-w-0 ${isKai ? 'text-[#0f766e]' : ''}`}>
                        {displayContent}
                        {isStreamingThis && kaiStreamingDisplayedLength < kaiStreamingContent!.length && (
                          <span className="inline-block w-2 h-4 ml-0.5 bg-[#0D9488] animate-pulse" aria-hidden />
                        )}
                      </p>
                      {isKai && (kaiDebugByMessageId[m.id] != null) && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setDebugModalMessageId(m.id); }}
                          className="shrink-0 p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
                          aria-label="Show LLM debug"
                        >
                          <Bug size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                  <span
                    className={`text-[9px] font-mono uppercase block mt-1 ${
                      isKai ? 'text-[#0D9488]' : 'text-slate-400'
                    }`}
                  >
                    {m.sender_name ?? (isYou ? 'You' : 'Other')}
                  </span>
                </div>
              </div>
            );
          })}
          {kaiTyping && (
            <div className="flex gap-3">
              <div className="w-8 h-8 shrink-0 flex items-center justify-center font-bold text-xs bg-[#0D9488] text-white">
                K
              </div>
              <div className="max-w-[85%]">
                <div className="p-3 shadow-[4px_4px_0px_0px_rgba(15,23,42,0.2)] bg-[#F0FDFA] border-2 border-[#0D9488]">
                  <p className="text-sm text-[#0f766e] animate-pulse">typing...</p>
                </div>
                <span className="text-[9px] font-mono uppercase block mt-1 text-[#0D9488]">Kai</span>
              </div>
            </div>
          )}
          {hasScreenshotAnalysis && (
            <>
              <div className="flex gap-3">
                <div className="w-8 h-8 shrink-0 flex items-center justify-center font-bold text-xs bg-slate-600 text-white border-2 border-slate-400">
                  <Camera size={14} strokeWidth={2.5} />
                </div>
                <div className="max-w-[85%]">
                  <div className="p-3 bg-white border-2 border-slate-200 border-l-4 border-slate-500 shadow-[2px_2px_0px_0px_rgba(15,23,42,0.06)] text-[11px] rounded-sm">
                    <p className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-2">From your screenshots</p>
                    <div className="space-y-2.5">
                      {screenshotMessageAnalysis!.message_analysis.map((a) => {
                        const showRevision = a.suggested_revision && a.guidance_type !== 'rephrase_that';
                        return (
                          <div key={a.message_index} className="text-slate-800">
                            <span className="font-semibold text-slate-700">{a.sender_label}:</span>{' '}
                            <span>{a.content}</span>
                            {showRevision && (
                              <div className="mt-1 text-amber-700 bg-amber-50 rounded px-1.5 py-1 text-[10px]">
                                <span className="font-mono font-bold uppercase">Suggested revision:</span> {a.suggested_revision}
                              </div>
                            )}
                            {a.guidance_type && a.guidance_text && (
                              <div className="mt-1 text-teal-800 bg-teal-50 rounded px-1.5 py-1 text-[10px]">
                                <span className="font-mono font-bold uppercase">{a.guidance_type.replace(/_/g, ' ')}:</span> {a.guidance_text}
                                {a.suggested_phrase && (
                                  <div className="mt-0.5 text-teal-700 italic">&ldquo;{a.suggested_phrase}&rdquo;</div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <span className="text-[9px] font-mono uppercase block mt-1 text-slate-500">Transcript + guidance</span>
                </div>
              </div>
              {kaiMessageAfterAnalysis && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 shrink-0 flex items-center justify-center font-bold text-xs bg-[#0D9488] text-white">
                    K
                  </div>
                  <div className="max-w-[85%]">
                    <div className="p-3 shadow-[4px_4px_0px_0px_rgba(15,23,42,0.2)] bg-[#F0FDFA] border-2 border-[#0D9488]">
                      <p className="text-sm text-[#0f766e]">{kaiMessageAfterAnalysis.content}</p>
                    </div>
                    <span className="text-[9px] font-mono uppercase block mt-1 text-[#0D9488]">Kai</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="relative shrink-0">
          <button
            type="button"
            onClick={() => {
              setPrivateWindowAnimateOpen(false);
              setPrivateWindowOpen(true);
              if (selectedRoomId) loadPrivateMessages(selectedRoomId);
            }}
            className="absolute bottom-full right-4 mb-2 flex items-center justify-center gap-1.5 py-1.5 px-2.5 border border-[#0D9488]/40 bg-[#F0FDFA] font-mono text-[9px] uppercase text-[#0D9488] hover:bg-[#0D9488]/10 transition-colors shadow-md z-10"
          >
            <Lock size={10} className="text-[#0D9488]" /> Talk to Kai in private
          </button>
        <footer className="p-4 bg-white border-t-4 border-[#1A1A1A] shrink-0 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
            {vetSuggestion ? (
              <div className="w-full sm:w-auto shrink-0 flex items-center gap-2 bg-orange-500/5 border border-orange-500/40 px-2.5 py-1.5 text-[9px] font-bold uppercase text-[#EA580C] max-w-md">
                {horsemanIcon(vetSuggestion.horseman, 12, 'text-[#EA580C] shrink-0')}
                <span className="min-w-0 flex-1 line-clamp-2">{vetSuggestion.suggestion}</span>
                <button
                  type="button"
                  onClick={() => {
                    setPublicInput((vetSuggestion.revised_text?.trim()) ? vetSuggestion.revised_text!.trim() : vetSuggestion.suggestion);
                    setVetSuggestion(null);
                  }}
                  className="shrink-0 font-mono border border-[#EA580C] bg-white/80 px-2 py-0.5 text-[#EA580C] hover:bg-orange-50 transition-colors"
                >
                  Revise for me
                </button>
              </div>
            ) : null}
            {guidance?.guidance_type ? (() => {
              const guidanceColors = (): { text: string; bg: string; border: string; icon: string } => {
                const t = guidance!.guidance_type;
                if (t === 'rephrase_that') return { text: 'text-[#059669]', bg: 'bg-emerald-500/5', border: 'border-emerald-500/40', icon: 'text-[#059669]' };
                if (t === 'analysis') return { text: 'text-[#2563EB]', bg: 'bg-blue-500/5', border: 'border-blue-500/40', icon: 'text-[#2563EB]' };
                return { text: 'text-[#059669]', bg: 'bg-emerald-500/5', border: 'border-emerald-500/40', icon: 'text-[#059669]' };
              };
              const c = guidanceColors();
              const isRephrase = guidance!.guidance_type === 'rephrase_that';
              const suggestedPhrase = (guidance!.suggested_phrase ?? '').trim();
              const openPrivateOnClick =
                guidance!.guidance_type !== 'analysis' && guidance!.guidance_type !== 'validate_feelings';
              const handleGuidanceClick = (e: React.MouseEvent) => {
                if (isRephrase && suggestedPhrase) {
                  setPublicInput(suggestedPhrase);
                  return;
                }
                if (!openPrivateOnClick) return; // analysis and validate_feelings: guidance is read-only in chip
                const rect = e.currentTarget.getBoundingClientRect();
                guidanceTriggerRectRef.current = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                const content = guidance!.text ?? guidance!.guidance_type.replace(/_/g, ' ');
                setGuidanceAsPrivateMessage({
                  id: `guidance-${Date.now()}`,
                  room_id: selectedRoomId!,
                  sender_user_id: null,
                  sender_name: 'Kai',
                  content,
                  visibility: 'private_to_kai',
                  sequence: 0,
                  created_at: new Date().toISOString(),
                });
                setPrivateWindowAnimateOpen(false);
                setPrivateWindowOpen(true);
                if (selectedRoomId) loadPrivateMessages(selectedRoomId);
              };
              return (
                <span className="flex w-full min-w-0 gap-1 sm:inline-flex sm:w-auto sm:flex-1 max-w-full">
                  <button
                    type="button"
                    onClick={handleGuidanceClick}
                    className={`min-w-0 max-w-full flex items-center gap-1.5 ${c.bg} border ${c.border} px-2.5 py-1 text-[9px] font-bold uppercase ${c.text} text-left whitespace-normal break-words ${openPrivateOnClick ? 'cursor-pointer hover:opacity-90 transition-opacity' : 'cursor-default'}`}
                    title={isRephrase && (guidance.suggested_phrase ?? '').trim() ? 'Click to use suggested phrase' : undefined}
                  >
                    <Zap size={10} className={`shrink-0 ${c.icon}`} />
                    <span className="min-w-0 flex-1 text-left break-words">{guidance.text ?? guidance.guidance_type.replace(/_/g, ' ')}</span>
                    {isRephrase && (guidance.suggested_phrase ?? '').trim() && (
                      <Edit3 size={10} className={`shrink-0 ${c.icon}`} aria-label="Click to use suggested phrase" />
                    )}
                  </button>
                  {(guidance.debug_prompt != null || guidance.debug_response != null) && (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setDebugModalMessageId('guidance'); }}
                      className="shrink-0 p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
                      aria-label="Show LLM debug"
                    >
                      <Bug size={12} />
                    </button>
                  )}
                </span>
              );
            })() : (
              <span />
            )}
          </div>
          {(voucherSuggestions?.length ?? 0) > 0 ? (
            <div className="rounded border border-[#059669]/40 bg-emerald-500/5 p-2 space-y-1">
              <p className="text-[9px] font-mono font-bold uppercase text-[#059669]">You could offer</p>
              <ul className="list-none space-y-1">
                {voucherSuggestions!.map((v, i) => (
                  <li key={i} className="text-xs text-[#1A1A1A]">
                    <span className="font-semibold">{v.title}</span>
                    <span className="block text-slate-600 mt-0.5">{v.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex flex-col gap-1">
            <label className="text-[9px] font-mono font-bold text-[#3B82F6] uppercase ml-1 flex items-center gap-1">
              <Send size={10} /> Send to chat group
            </label>
            <form
              className="flex gap-0 shadow-lg"
              onSubmit={(e) => {
                e.preventDefault();
                handleSendPublic();
              }}
            >
              <input
                type="text"
                value={publicInput}
                onChange={(e) => setPublicInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSendPublic();
                  }
                }}
                placeholder="Send message..."
                className="flex-1 border-2 border-[#1A1A1A] bg-white px-4 py-3 font-mono text-sm uppercase placeholder:text-slate-400 font-bold h-14"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={!publicInput.trim() || loading}
                className="w-16 h-14 bg-[#3B82F6] text-white flex items-center justify-center disabled:opacity-50"
              >
                <Send size={20} />
              </button>
            </form>
          </div>
          <div className="flex justify-between items-center text-[9px] font-mono text-slate-400">
            <button type="button" onClick={() => setSelectedRoomId(null)} className="uppercase hover:text-[#1A1A1A]">
              Back to chat groups
            </button>
            <span>{members.length + 1} in chat group</span>
          </div>
        </footer>
        </div>
      </div>
    </div>
  );
};
