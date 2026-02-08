import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  ActivityMemoryItem,
  ScrapbookLayout,
  ElementScrapbookLayout,
  isElementScrapbookLayout,
  AddNotificationFn,
} from '../../../shared/types/domain';
import {
  BookHeart,
  Camera,
  Loader2,
  Plus,
  X,
  Save,
  Image as ImageIcon,
  Trash2,
  RotateCw,
  CheckCircle2,
  Circle,
  Sparkles,
  Users,
  GitMerge,
  Palette,
  Bug,
} from 'lucide-react';
import { Modal } from '@/src/shared/ui/Modal';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import {
  useActivityMemoriesQuery,
  useCompletePlannedActivityMutation,
  useDiscoverFeedQuery,
  usePlannedActivitiesQuery,
  useSentActivityInvitesQuery,
  useActivityHistoryAllQuery,
} from '../api/activities.mutations';
import { apiService } from '../../../shared/api/apiService';
import { processImageForUpload, pickActivityImages } from '../../../shared/utils/imageUpload';

/** Feeling/vibe options for scrapbook "Log Memory" form (Vibe Check); label sent to API (lowercase). */
const FEELINGS_WITH_EMOJI = [
  { label: 'Happy', icon: '😄', value: 'happy' },
  { label: 'Loved', icon: '🥰', value: 'loved' },
  { label: 'Excited', icon: '🤩', value: 'excited' },
  { label: 'Relaxed', icon: '😌', value: 'relaxed' },
  { label: 'Playful', icon: '😜', value: 'playful' },
  { label: 'Connected', icon: '🤝', value: 'connected' },
] as const;

function processHtmlContent(html: string, imageUrls: string[]): string {
  if (!html) return '';
  let processed = html;
  imageUrls.forEach((url, idx) => {
    const regex = new RegExp(`\\{\\{USER_IMAGE_${idx}\\}\\}|USER_IMAGE_${idx}`, 'g');
    processed = processed.replace(regex, url);
  });
  processed = processed.replace(/\{\{USER_IMAGE_\d+\}\}|USER_IMAGE_\d+/g, 'https://via.placeholder.com/300?text=No+Image');
  return processed;
}

function ScrapbookHtml({
  html,
  className,
  style,
}: {
  html: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !html) return;
    const stickers = el.querySelectorAll('img.sticker');
    const cleanups: (() => void)[] = [];
    stickers.forEach((img) => {
      const imgEl = img as HTMLImageElement;
      const hideAndLog = (reason: string) => {
        imgEl.style.display = 'none';
        const srcPreview = imgEl.src ? `${imgEl.src.slice(0, 60)}...` : '(no src)';
        console.error('[Scrapbook] Sticker failed to load:', reason, srcPreview);
      };
      if (!imgEl.src || imgEl.src.trim() === '') {
        hideAndLog('missing or empty src');
        return;
      }
      const onError = () => hideAndLog('image load error');
      imgEl.addEventListener('error', onError);
      cleanups.push(() => imgEl.removeEventListener('error', onError));
    });
    return () => cleanups.forEach((c) => c());
  }, [html]);
  return (
    <div
      ref={ref}
      className={className}
      style={style}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function renderElementScrapbookLayout(layout: ElementScrapbookLayout, imageUrls: string[]) {
  const containerStyle: React.CSSProperties = {
    backgroundColor: layout.bgStyle.color,
    backgroundImage:
      layout.bgStyle.texture === 'dot-grid'
        ? 'radial-gradient(#cbd5e1 1px, transparent 1px)'
        : layout.bgStyle.texture === 'paper'
          ? 'url("https://www.transparenttextures.com/patterns/cardboard-flat.png")'
          : 'none',
    backgroundSize: '20px 20px',
  };
  return (
    <div
      className="relative overflow-hidden w-full shadow-lg transition-all hover:shadow-xl border-4 border-white aspect-[3/4]"
      style={containerStyle}
    >
      {layout.elements.map((el, i) => {
        const commonStyle: React.CSSProperties = {
          position: 'absolute',
          top: el.style.top,
          left: el.style.left,
          width: el.style.width || 'auto',
          transform: `rotate(${el.style.rotation})`,
          zIndex: el.style.zIndex,
          textAlign: (el.style.textAlign as 'left' | 'center' | 'right') || 'left',
          fontFamily: el.style.fontFamily === 'handwritten' ? 'cursive' : el.style.fontFamily,
          fontSize: el.style.fontSize,
          color: el.style.color,
          backgroundColor: el.style.background,
          borderRadius: el.style.borderRadius,
          boxShadow: el.style.boxShadow || '2px 2px 5px rgba(0,0,0,0.1)',
        };
        if (el.type === 'text') {
          return (
            <div key={i} style={commonStyle} className="p-2">
              {el.content}
            </div>
          );
        }
        if (el.type === 'image') {
          const imgIndex = parseInt(el.content, 10);
          const src = imageUrls[imgIndex];
          if (!src) return null;
          return (
            <div key={i} style={commonStyle} className="bg-white p-2">
              <div className="w-full h-full overflow-hidden aspect-square">
                <img src={src} alt="Memory" className="w-full h-full object-cover" />
              </div>
            </div>
          );
        }
        if (el.type === 'sticker' || el.type === 'doodle') {
          return (
            <div
              key={i}
              style={{ ...commonStyle, boxShadow: 'none', background: 'transparent' }}
              className="text-4xl pointer-events-none select-none"
            >
              {el.content}
            </div>
          );
        }
        if (el.type === 'tape') {
          return <div key={i} style={{ ...commonStyle, height: '15px', opacity: 0.8 }} />;
        }
        return null;
      })}
    </div>
  );
}

export interface MemoryScrapbookViewProps {
  onAddNotification?: AddNotificationFn;
}

export const MemoryScrapbookView: React.FC<MemoryScrapbookViewProps> = ({ onAddNotification }) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  const firstRelationshipId = relationships?.[0]?.relationshipId;

  const [completeModal, setCompleteModal] = useState<{ plannedId: string | null; title: string } | null>(null);
  const [completeActivityTitle, setCompleteActivityTitle] = useState('');
  const [isAddingMemory, setIsAddingMemory] = useState(false);
  const [magicDesignMemId, setMagicDesignMemId] = useState<string | null>(null);
  const [generatedLayout, setGeneratedLayout] = useState<ScrapbookLayout | null>(null);
  const [generatedOptionsFromCard, setGeneratedOptionsFromCard] = useState<ElementScrapbookLayout[] | null>(null);
  const [generatedHtmlFromCard, setGeneratedHtmlFromCard] = useState<string | null>(null);
  const [scrapbookDebugPrompt, setScrapbookDebugPrompt] = useState<string | null>(null);
  const [scrapbookDebugResponse, setScrapbookDebugResponse] = useState<string | null>(null);
  const [scrapbookDebugModalOpen, setScrapbookDebugModalOpen] = useState(false);
  const [selectedOptionIndexFromCard, setSelectedOptionIndexFromCard] = useState(0);
  const [isGeneratingLayout, setIsGeneratingLayout] = useState(false);
  const [saveScrapbookPending, setSaveScrapbookPending] = useState(false);
  const [completeFeeling, setCompleteFeeling] = useState<string | null>(null);
  const [completeNotes, setCompleteNotes] = useState('');
  const [completeFiles, setCompleteFiles] = useState<File[]>([]);
  const completeFileInputRef = useRef<HTMLInputElement>(null);
  const [completeFileCaptions, setCompleteFileCaptions] = useState<Record<number, string>>({});
  const [completeParticipants, setCompleteParticipants] = useState<string[]>([]);
  const [generatedOptionsFromForm, setGeneratedOptionsFromForm] = useState<ElementScrapbookLayout[] | null>(null);
  const [selectedOptionIndexFromForm, setSelectedOptionIndexFromForm] = useState(0);
  const [isGeneratingLayoutFromForm, setIsGeneratingLayoutFromForm] = useState(false);
  const [scrollToNewMemory, setScrollToNewMemory] = useState(false);
  const firstMemoryCardRef = useRef<HTMLDivElement | null>(null);

  const showDebug = user?.preferences?.showDebug ?? true;
  const otherMembers = relationships?.length
    ? relationships.map((r) => ({ id: r.id, name: r.name }))
    : user?.lovedOnes?.map((l) => ({ id: l.id, name: l.name })) ?? [];

  const memoriesQuery = useActivityMemoriesQuery(firstRelationshipId ?? undefined);
  const completeMutation = useCompletePlannedActivityMutation();
  const discoverFeedQuery = useDiscoverFeedQuery(firstRelationshipId ?? undefined);
  const plannedQuery = usePlannedActivitiesQuery(firstRelationshipId ?? undefined);
  const sentInvitesQuery = useSentActivityInvitesQuery();
  const historyAllQuery = useActivityHistoryAllQuery(firstRelationshipId ?? undefined);

  const discoverActivities = React.useMemo(() => {
    const raw = discoverFeedQuery.data ?? [];
    return raw.length > 0 ? [...raw].reverse() : raw;
  }, [discoverFeedQuery.data]);

  const filteredActivities = discoverActivities;
  const memoriesItems = (memoriesQuery.data as any[]) ?? [];

  useEffect(() => {
    if (!scrollToNewMemory || memoriesItems.length === 0) return;
    const el = firstMemoryCardRef.current;
    if (el) {
      requestAnimationFrame(() => {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      setScrollToNewMemory(false);
    } else {
      setScrollToNewMemory(false);
    }
  }, [scrollToNewMemory, memoriesItems.length]);

  const MEMORY_MAX_BYTES = 5 * 1024 * 1024;

  const handleCompletePlanned = async () => {
    if (!completeModal) return;
    const isStandalone = completeModal.plannedId === null;
    const relationshipId = firstRelationshipId;
    if (isStandalone && !relationshipId) {
      onAddNotification?.('system', 'Missing relationship', 'Please select a relationship before logging a memory.');
      return;
    }
    const urls: string[] = [];
    const memoryEntries: { url: string; caption?: string }[] = [];
    try {
      for (let i = 0; i < completeFiles.length; i++) {
        const file = completeFiles[i];
        if (file.size > MEMORY_MAX_BYTES) {
          onAddNotification?.('system', 'File too large', `"${file.name}" is over 5MB. Please choose a smaller image.`);
          return;
        }
        let res;
        try {
          res = isStandalone && relationshipId
            ? await apiService.uploadRelationshipMemory(relationshipId, file)
            : await apiService.uploadActivityMemory(completeModal.plannedId as string, file);
        } catch (uploadErr: unknown) {
          const msg = uploadErr instanceof Error ? uploadErr.message : `"${file.name}" could not be uploaded.`;
          onAddNotification?.('system', 'Upload failed', msg);
          return;
        }
        const data = res.data as { url?: string };
        if (data?.url) {
          urls.push(data.url);
          memoryEntries.push({ url: data.url, caption: completeFileCaptions[i]?.trim() || undefined });
        }
      }
      if (isStandalone && relationshipId) {
        const activityTitle = completeActivityTitle.trim() || completeModal.title || 'Memory';
        await apiService.logMemory({
          relationship_id: relationshipId,
          activity_title: activityTitle,
          notes: completeNotes.trim() || undefined,
          memory_urls: urls.length ? urls : undefined,
          memory_entries: memoryEntries.length ? memoryEntries : undefined,
          feeling: completeFeeling ?? undefined,
        });
        onAddNotification?.('system', 'Memory saved', activityTitle);
      } else {
        await completeMutation.mutateAsync({
          plannedId: completeModal.plannedId as string,
          notes: completeNotes.trim() || undefined,
          memory_urls: urls.length ? urls : undefined,
          memory_entries: memoryEntries.length ? memoryEntries : undefined,
          feeling: completeFeeling ?? undefined,
        });
        onAddNotification?.('system', 'Activity logged', `${completeModal.title} completed. +100 XP`);
      }
      setCompleteNotes('');
      setCompleteFiles([]);
      setCompleteFileCaptions({});
      setCompleteFeeling(null);
      setIsAddingMemory(false);
      closeCompleteModal();
      await memoriesQuery.refetch();
      historyAllQuery.refetch();
      plannedQuery.refetch();
      sentInvitesQuery.refetch();
      setScrollToNewMemory(true);
    } catch (e) {
      console.error(e);
      alert('Failed to complete activity.');
    }
  };

  const closeCompleteModal = () => {
    setCompleteModal(null);
    setCompleteActivityTitle('');
    setCompleteNotes('');
    setCompleteFiles([]);
    setCompleteFileCaptions({});
    setCompleteFeeling(null);
    setCompleteParticipants([]);
    setGeneratedOptionsFromForm(null);
    setIsAddingMemory(false);
    setMagicDesignMemId(null);
    setGeneratedLayout(null);
    setGeneratedOptionsFromCard(null);
    setGeneratedHtmlFromCard(null);
    setScrapbookDebugPrompt(null);
    setScrapbookDebugResponse(null);
  };

  const runMagicDesign = async (mem: ActivityMemoryItem, singleStyle?: boolean) => {
    const contributions = [...(mem.contributions ?? [])].sort((a, b) => (a.actor_user_id === user?.id ? -1 : b.actor_user_id === user?.id ? 1 : 0));
    const allEntries = contributions.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name, actor_user_id: c.actor_user_id })));
    const note = contributions.map((c) => c.notes_text).filter(Boolean).join(' ') || 'A moment we shared.';
    const feeling = contributions.find((c) => c.feeling)?.feeling ?? undefined;
    setIsGeneratingLayout(true);
    setMagicDesignMemId(mem.id);
    setGeneratedLayout(null);
    setGeneratedOptionsFromCard(null);
    setGeneratedHtmlFromCard(null);
    setScrapbookDebugPrompt(null);
    setScrapbookDebugResponse(null);
    try {
      if (singleStyle) {
        const scrapbookStickersEnabled = user?.preferences?.scrapbookStickersEnabled ?? false;
        const res = await apiService.generateScrapbookHtml({
          activity_title: mem.activity_title,
          note,
          feeling: feeling ?? undefined,
          image_count: allEntries.length,
          activity_template_id: mem.activity_template_id ?? undefined,
          include_debug: showDebug,
          disable_sticker_generation: !scrapbookStickersEnabled,
        });
        const data = res.data as { htmlContent: string; prompt?: string; response?: string };
        const html = data.htmlContent;
        if (html) {
          setGeneratedHtmlFromCard(html);
          if (showDebug && (data.prompt != null || data.response != null)) {
            setScrapbookDebugPrompt(data.prompt ?? null);
            setScrapbookDebugResponse(data.response ?? null);
          } else {
            setScrapbookDebugPrompt(null);
            setScrapbookDebugResponse(null);
          }
        } else {
          const fallback = await apiService.generateScrapbookOptions({
            activity_title: mem.activity_title,
            note,
            feeling: feeling ?? undefined,
            image_count: allEntries.length,
            limit: 1,
          });
          const options = (fallback.data as { options: ElementScrapbookLayout[] }).options ?? [];
          if (options.length > 0) {
            setGeneratedOptionsFromCard(options);
            setSelectedOptionIndexFromCard(0);
          } else {
            const layoutRes = await apiService.generateScrapbookLayout({
              activity_title: mem.activity_title,
              note,
              feeling: feeling ?? undefined,
              image_count: allEntries.length,
            });
            setGeneratedLayout(layoutRes.data as ScrapbookLayout);
          }
        }
        return;
      }
      const res = await apiService.generateScrapbookOptions({
        activity_title: mem.activity_title,
        note,
        feeling: feeling ?? undefined,
        image_count: allEntries.length,
        limit: 3,
      });
      const options = (res.data as { options: ElementScrapbookLayout[] }).options ?? [];
      if (options.length > 0) {
        setGeneratedOptionsFromCard(options);
        setSelectedOptionIndexFromCard(0);
      } else {
        const fallback = await apiService.generateScrapbookLayout({
          activity_title: mem.activity_title,
          note,
          feeling: feeling ?? undefined,
          image_count: allEntries.length,
        });
        setGeneratedLayout(fallback.data as ScrapbookLayout);
      }
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : 'Failed to generate scrapbook design.';
      onAddNotification?.('system', 'Scrapbook generation failed', msg);
      setGeneratedLayout(null);
      setGeneratedOptionsFromCard(null);
      setGeneratedHtmlFromCard(null);
      setScrapbookDebugPrompt(null);
      setScrapbookDebugResponse(null);
      setMagicDesignMemId(null);
    } finally {
      setIsGeneratingLayout(false);
    }
  };

  const runMagicDesignFromForm = async () => {
    if (!completeModal) return;
    setIsGeneratingLayoutFromForm(true);
    try {
      const res = await apiService.generateScrapbookOptions({
        activity_title: completeActivityTitle.trim() || completeModal.title,
        note: completeNotes.trim() || 'A moment we shared.',
        feeling: completeFeeling ?? undefined,
        image_count: completeFiles.length,
      });
      const options = (res.data as { options: ElementScrapbookLayout[] }).options ?? [];
      setGeneratedOptionsFromForm(options.length > 0 ? options : null);
      setSelectedOptionIndexFromForm(0);
    } catch (e) {
      console.error(e);
      setGeneratedOptionsFromForm(null);
    } finally {
      setIsGeneratingLayoutFromForm(false);
    }
  };

  const saveScrapbookFromForm = async () => {
    if (!completeModal || !generatedOptionsFromForm?.length) return;
    if (completeModal.plannedId === null) {
      onAddNotification?.('system', 'Not yet supported', 'Standalone memory logging requires backend support.');
      closeCompleteModal();
      return;
    }
    const layout = generatedOptionsFromForm[selectedOptionIndexFromForm];
    if (!layout) return;
    setSaveScrapbookPending(true);
    try {
      await handleCompletePlanned();
      await apiService.saveScrapbook(completeModal.plannedId, layout as unknown as Record<string, unknown>);
      onAddNotification?.('system', 'Scrapbook saved', 'Your shared memory has a new layout.');
      setGeneratedOptionsFromForm(null);
      closeCompleteModal();
      await memoriesQuery.refetch();
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : 'Failed to save scrapbook.';
      onAddNotification?.('system', 'Scrapbook save failed', msg);
    } finally {
      setSaveScrapbookPending(false);
    }
  };

  const saveScrapbookLayout = async () => {
    const layoutToSave = generatedHtmlFromCard
      ? { htmlContent: generatedHtmlFromCard }
      : generatedOptionsFromCard?.length
        ? generatedOptionsFromCard[selectedOptionIndexFromCard]
        : generatedLayout;
    if (!layoutToSave) return;
    const plannedId = completeModal?.plannedId ?? magicDesignMemId;
    if (!plannedId) return;
    setSaveScrapbookPending(true);
    try {
      await apiService.saveScrapbook(plannedId, layoutToSave as unknown as Record<string, unknown>);
      onAddNotification?.('system', 'Scrapbook saved', 'Your shared memory has a new layout. All participants were notified.');
      setGeneratedLayout(null);
      setGeneratedOptionsFromCard(null);
      setGeneratedHtmlFromCard(null);
      setMagicDesignMemId(null);
      await memoriesQuery.refetch();
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : 'Failed to save scrapbook.';
      onAddNotification?.('system', 'Scrapbook save failed', msg);
      alert(msg);
    } finally {
      setSaveScrapbookPending(false);
    }
  };

  if (!user) return null;

  return (
    <>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="font-black text-slate-900 uppercase tracking-tighter text-lg flex items-center gap-2">
            <BookHeart size={20} className="text-slate-900" /> Scrapbook
          </h3>
          <button
            type="button"
            onClick={() => {
              setCompleteModal({ plannedId: null, title: '' });
              setIsAddingMemory(true);
              memoriesQuery.refetch();
            }}
            className="bg-slate-900 text-white text-[10px] font-bold uppercase tracking-widest px-4 py-2 flex items-center gap-2 hover:bg-slate-800 transition-colors shadow-lg active:translate-y-0.5 active:shadow-none"
          >
            <Plus size={14} /> Log Memory
          </button>
        </div>
        {memoriesItems.length === 0 && (
          <div className="text-center py-12 border-2 border-dashed border-slate-300 bg-slate-50">
            <Camera size={32} className="mx-auto text-slate-300 mb-2" />
            <p className="text-xs font-mono text-slate-500 uppercase">No memories archived.</p>
          </div>
        )}
        <div className="grid grid-cols-1 gap-6">
          {(memoriesItems as ActivityMemoryItem[]).map((mem, index) => {
            const contributions = [...(mem.contributions ?? [])].sort((a, b) => (a.actor_user_id === user?.id ? -1 : b.actor_user_id === user?.id ? 1 : 0));
            const allEntries = contributions.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name, actor_user_id: c.actor_user_id })));
            const isShared = contributions.length > 1;
            const entriesForLayout = contributions.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name })));
            const imageUrlsForMem = entriesForLayout.map((e) => apiService.getMemoryImageUrl(e.url));
            const discardEnhance = () => {
              setGeneratedLayout(null);
              setGeneratedOptionsFromCard(null);
              setGeneratedHtmlFromCard(null);
              setScrapbookDebugPrompt(null);
              setScrapbookDebugResponse(null);
              setMagicDesignMemId(null);
            };

            if (magicDesignMemId === mem.id) {
              return (
                <div key={mem.id} ref={index === 0 ? firstMemoryCardRef : undefined} className="bg-slate-100 border-2 border-indigo-600 p-4 shadow-xl">
                  <div className="flex items-center justify-between mb-4 pb-2 border-b border-indigo-200">
                    <div className="flex items-center gap-2 text-indigo-700 font-bold text-xs uppercase">
                      {isGeneratingLayout ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      SCRAPBOOKING...
                    </div>
                    <button type="button" onClick={discardEnhance} className="text-[10px] text-slate-500 hover:text-indigo-600 underline font-mono">
                      Cancel
                    </button>
                  </div>
                  {isGeneratingLayout ? (
                    <div className="py-12 text-center text-slate-400 font-mono text-xs uppercase animate-pulse">
                      Generating designs...
                    </div>
                  ) : generatedHtmlFromCard ? (
                    <>
                      <div className="flex items-center justify-between mb-2">
                        {showDebug && (scrapbookDebugPrompt != null || scrapbookDebugResponse != null) && (
                          <button
                            type="button"
                            onClick={() => setScrapbookDebugModalOpen(true)}
                            className="flex items-center gap-1 text-[10px] font-bold text-slate-500 uppercase tracking-widest hover:text-slate-700"
                            title="View prompt and response"
                          >
                            <Bug size={12} /> Debug
                          </button>
                        )}
                        <span className="flex-1" />
                      </div>
                      <div className="mb-4 bg-white border border-slate-200 overflow-hidden rounded">
                        <ScrapbookHtml
                          html={processHtmlContent(generatedHtmlFromCard, imageUrlsForMem)}
                          className="scrapbook-content w-full min-h-[200px]"
                          style={{ isolation: 'isolate' }}
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          saveScrapbookLayout();
                          discardEnhance();
                          memoriesQuery.refetch();
                        }}
                        disabled={saveScrapbookPending}
                        className="w-full bg-indigo-600 text-white py-3 font-bold uppercase tracking-widest text-xs shadow-md border-2 border-indigo-800 active:translate-y-0.5 active:shadow-none disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                        Apply Design
                      </button>
                    </>
                  ) : generatedOptionsFromCard && generatedOptionsFromCard.length > 0 ? (
                    <>
                      {generatedOptionsFromCard.length > 1 && (
                        <div className="flex gap-2 mb-4 overflow-x-auto no-scrollbar pb-1">
                          {generatedOptionsFromCard.map((opt, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => setSelectedOptionIndexFromCard(idx)}
                              className={`flex-1 min-w-[80px] py-2 px-1 text-[9px] font-bold uppercase border-2 transition-all ${
                                selectedOptionIndexFromCard === idx ? 'bg-indigo-600 text-white border-indigo-800 shadow-md' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                              }`}
                            >
                              {opt.styleName}
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="mb-4 bg-white border border-slate-200">
                        {generatedOptionsFromCard[selectedOptionIndexFromCard] &&
                          renderElementScrapbookLayout(generatedOptionsFromCard[selectedOptionIndexFromCard], imageUrlsForMem)}
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          saveScrapbookLayout();
                          discardEnhance();
                          memoriesQuery.refetch();
                        }}
                        disabled={saveScrapbookPending}
                        className="w-full bg-indigo-600 text-white py-3 font-bold uppercase tracking-widest text-xs shadow-md border-2 border-indigo-800 active:translate-y-0.5 active:shadow-none disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                        Apply Design
                      </button>
                    </>
                  ) : generatedLayout ? (
                    <>
                      <div className="max-w-[280px] mx-auto mb-4 bg-white border border-slate-200 p-2">
                        <div className="relative overflow-hidden p-4 shadow-lg rounded" style={{ backgroundColor: generatedLayout.themeColor }}>
                          <div className="absolute top-2 right-2 text-2xl z-10">{generatedLayout.stickers[0]}</div>
                          <div className="text-center mb-2">
                            <h3 className="font-black text-lg uppercase tracking-tighter" style={{ color: generatedLayout.secondaryColor }}>
                              {generatedLayout.headline}
                            </h3>
                          </div>
                          <div className="bg-white/80 backdrop-blur-sm p-2 rounded">
                            <p className="font-serif text-slate-800 text-sm italic text-center">&quot;{generatedLayout.narrative}&quot;</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={() => runMagicDesign(mem)} className="flex-1 bg-white border-2 border-slate-200 font-bold uppercase tracking-widest py-2.5 text-xs">
                          Regenerate
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            saveScrapbookLayout();
                            discardEnhance();
                            memoriesQuery.refetch();
                          }}
                          disabled={saveScrapbookPending}
                          className="flex-[2] bg-indigo-600 text-white font-bold uppercase tracking-widest py-2.5 border-2 border-indigo-800 disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                          {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Apply Design
                        </button>
                      </div>
                    </>
                  ) : null}
                </div>
              );
            }

            if (mem.scrapbook_layout && 'htmlContent' in mem.scrapbook_layout && typeof (mem.scrapbook_layout as { htmlContent?: string }).htmlContent === 'string') {
              const htmlContent = (mem.scrapbook_layout as { htmlContent: string }).htmlContent;
              return (
                <div key={mem.id} ref={index === 0 ? firstMemoryCardRef : undefined} className="relative group">
                  {isShared && (
                    <div className="absolute -top-3 left-4 z-20 bg-indigo-600 text-white px-3 py-1 text-[9px] font-bold uppercase tracking-widest shadow-md flex items-center gap-1 rounded-full">
                      <GitMerge size={10} /> Shared
                    </div>
                  )}
                  <ScrapbookHtml
                    html={processHtmlContent(htmlContent, imageUrlsForMem)}
                    className="scrapbook-content w-full min-h-[200px] shadow-lg transition-all hover:shadow-xl border-4 border-white overflow-hidden"
                    style={{ isolation: 'isolate' }}
                  />
                  <div className="absolute top-4 right-4 z-20 opacity-90 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() => runMagicDesign(mem, true)}
                      className="bg-white/90 text-indigo-600 p-2 rounded-full shadow-lg border border-indigo-100 hover:bg-indigo-50"
                      title="Change Style"
                      aria-label="Change style / regenerate scrapbook"
                    >
                      <Palette size={16} />
                    </button>
                  </div>
                </div>
              );
            }
            if (mem.scrapbook_layout && isElementScrapbookLayout(mem.scrapbook_layout)) {
              return (
                <div key={mem.id} ref={index === 0 ? firstMemoryCardRef : undefined} className="relative group">
                  {isShared && (
                    <div className="absolute -top-3 left-4 z-20 bg-indigo-600 text-white px-3 py-1 text-[9px] font-bold uppercase tracking-widest shadow-md flex items-center gap-1 rounded-full">
                      <GitMerge size={10} /> Shared
                    </div>
                  )}
                  {renderElementScrapbookLayout(mem.scrapbook_layout, imageUrlsForMem)}
                  <div className="absolute top-4 right-4 z-20 opacity-90 group-hover:opacity-100 transition-opacity">
                    <button
                      type="button"
                      onClick={() => runMagicDesign(mem, true)}
                      className="bg-white/90 text-indigo-600 p-2 rounded-full shadow-lg border border-indigo-100 hover:bg-indigo-50"
                      title="Change Style"
                      aria-label="Change style / regenerate scrapbook"
                    >
                      <Palette size={16} />
                    </button>
                  </div>
                </div>
              );
            }

            return (
              <div key={mem.id} ref={index === 0 ? firstMemoryCardRef : undefined} className="relative">
                {isShared && (
                  <div className="absolute -top-3 left-4 z-20 bg-indigo-600 text-white px-3 py-1 text-[9px] font-bold uppercase tracking-widest shadow-md flex items-center gap-1 rounded-full">
                    <GitMerge size={10} /> Shared
                  </div>
                )}
                <div className="bg-white border-2 border-slate-200 shadow-[4px_4px_0px_rgba(30,41,59,0.05)] hover:shadow-[4px_4px_0px_rgba(30,41,59,0.1)] transition-all">
                  <div className="p-4">
                    <div className="flex justify-between items-start mb-3 border-b border-slate-100 pb-2">
                      <div>
                        <h4 className="font-bold text-slate-900 text-sm uppercase">{mem.activity_title}</h4>
                        <span className="text-[9px] font-mono text-slate-400">{mem.completed_at ? new Date(mem.completed_at).toLocaleDateString() : ''}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 justify-end">
                        {(mem.contributions ?? []).filter((c) => c.feeling).map((c, i) => (
                          <span key={`${c.actor_user_id}-${i}`} className="bg-indigo-50 text-indigo-700 px-2 py-1 text-[9px] font-bold uppercase border border-indigo-200">
                            {c.feeling}
                          </span>
                        ))}
                      </div>
                    </div>
                    {mem.scrapbook_layout && !isElementScrapbookLayout(mem.scrapbook_layout) && (() => {
                      const sl = mem.scrapbook_layout as ScrapbookLayout;
                      return (
                        <div className="relative overflow-hidden p-4 shadow-lg border-2 border-slate-200 rounded-lg mb-4" style={{ backgroundColor: (sl as ScrapbookLayout).themeColor }}>
                          <div className="absolute top-4 left-4 -rotate-12 bg-white px-2 py-1 shadow-md border border-slate-200 z-10">
                            <p className="text-[8px] font-bold font-mono text-slate-400 uppercase tracking-widest">{mem.completed_at ? new Date(mem.completed_at).toLocaleDateString() : ''}</p>
                          </div>
                          <div className="absolute top-2 right-2 text-2xl z-10">{(sl as ScrapbookLayout).stickers[0]}</div>
                          {(sl as ScrapbookLayout).stickers[1] != null && (
                            <div className="absolute bottom-2 left-2 text-2xl z-10">{(sl as ScrapbookLayout).stickers[1]}</div>
                          )}
                          <div className="text-center mb-3">
                            <h3 className="font-black text-lg uppercase tracking-tighter" style={{ color: (sl as ScrapbookLayout).secondaryColor }}>
                              {(sl as ScrapbookLayout).headline}
                            </h3>
                            <div className="w-12 h-0.5 mx-auto mt-1 opacity-50" style={{ backgroundColor: (sl as ScrapbookLayout).secondaryColor }} />
                          </div>
                          <div className={`grid gap-2 mb-3 ${entriesForLayout.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                            {entriesForLayout.slice(0, (sl as ScrapbookLayout).imageCaptions.length).map((e, idx) => (
                              <div key={idx} className={`bg-white p-1.5 shadow-sm rounded transition-transform hover:rotate-0 hover:scale-105 ${idx % 2 === 0 ? '-rotate-2' : 'rotate-2'}`}>
                                <div className="aspect-square bg-slate-100 overflow-hidden mb-1 rounded">
                                  <img src={apiService.getMemoryImageUrl(e.url)} alt="" className="w-full h-full object-cover" />
                                </div>
                                <p className="font-serif italic text-xs text-center text-slate-600">{(sl as ScrapbookLayout).imageCaptions[idx] ?? 'Lovely moment'}</p>
                              </div>
                            ))}
                          </div>
                          <div className="bg-white/80 backdrop-blur-sm p-3 rounded border border-white/50">
                            <p className="font-serif text-slate-800 leading-relaxed italic text-center text-sm">&quot;{(sl as ScrapbookLayout).narrative}&quot;</p>
                          </div>
                          <div className="flex justify-center mt-3 -space-x-2">
                            {user?.id && (
                              <div className="w-7 h-7 rounded-full bg-white border-2 border-slate-200 flex items-center justify-center text-[10px] font-bold text-slate-900 shadow-sm">
                                {user.name?.charAt(0) ?? '?'}
                              </div>
                            )}
                            {contributions.filter((c) => c.actor_user_id !== user?.id).map((c) => (
                              <div key={c.actor_user_id} className="w-7 h-7 rounded-full bg-indigo-500 border-2 border-white flex items-center justify-center text-[10px] font-bold text-white shadow-sm">
                                {c.actor_name?.charAt(0) ?? '?'}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}
                    {allEntries.length > 0 && (
                      <div className="mb-4 overflow-x-auto overflow-y-hidden flex gap-0 snap-x snap-mandatory scroll-smooth -mx-1 px-1" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                        {allEntries.map((e, i) => (
                          <div key={i} className="flex-shrink-0 w-[85%] max-w-[280px] snap-start snap-always aspect-[4/3] bg-slate-100 border border-slate-200 overflow-hidden relative rounded">
                            <img src={apiService.getMemoryImageUrl(e.url)} alt={e.caption ?? 'Memory'} className="w-full h-full object-cover" />
                            {e.caption ? (
                              <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-2">{e.caption}</div>
                            ) : null}
                            <div
                              className={`absolute bottom-0 right-0 px-2 py-0.5 text-[8px] font-bold uppercase backdrop-blur-sm ${e.actor_user_id === user?.id ? 'bg-slate-900/90 text-white' : 'bg-indigo-600/90 text-white'}`}
                            >
                              {e.actor_user_id === user?.id ? 'You' : (e.actorName ?? 'Partner')}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {contributions.map((c) => {
                      if (!c.notes_text) return null;
                      const isUser = c.actor_user_id === user?.id;
                      return isUser ? (
                        <div key={c.actor_user_id} className="flex gap-3 mb-2">
                          <div className="w-6 h-6 bg-slate-900 text-white rounded-full flex items-center justify-center text-[9px] shrink-0 font-bold border-2 border-white shadow-sm mt-0.5">
                            {user?.name?.charAt(0) ?? '?'}
                          </div>
                          <div className="bg-slate-50 p-2 rounded-r-lg rounded-bl-lg text-slate-700 text-xs italic font-serif leading-relaxed border border-slate-100 flex-1">
                            &quot;{c.notes_text}&quot;
                          </div>
                        </div>
                      ) : (
                        <div key={c.actor_user_id} className="flex gap-3 mt-2 justify-end">
                          <div className="bg-indigo-50 p-2 rounded-l-lg rounded-br-lg text-indigo-900 text-xs italic font-serif leading-relaxed border border-indigo-100 flex-1 text-right">
                            &quot;{c.notes_text}&quot;
                          </div>
                          <div className="w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-[9px] shrink-0 font-bold border-2 border-white shadow-sm mt-0.5">
                            {c.actor_name?.charAt(0) ?? '?'}
                          </div>
                        </div>
                      );
                    })}
                    <div className="mt-3 pt-3 border-t border-slate-100 flex justify-end">
                      <button
                        type="button"
                        onClick={() => runMagicDesign(mem, true)}
                        disabled={isGeneratingLayout && magicDesignMemId === mem.id}
                        className="text-[10px] font-bold uppercase tracking-widest text-indigo-600 hover:text-indigo-800 flex items-center gap-1 disabled:opacity-50 transition-colors bg-indigo-50 px-3 py-1.5 border border-indigo-100 rounded"
                      >
                        {isGeneratingLayout && magicDesignMemId === mem.id ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                        Enhance
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Complete / Log Memory modal – portaled so it appears above the Master Suite header */}
      {completeModal &&
        createPortal(
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4" style={{ paddingTop: 'max(1rem, env(safe-area-inset-top))' }}>
            <div
              className={`bg-white border-2 border-slate-900 p-5 max-w-md w-full max-h-[90vh] flex flex-col ${
                (isAddingMemory || completeModal.plannedId === null) ? 'shadow-[8px_8px_0px_rgba(30,41,59,0.2)]' : 'shadow-xl'
              }`}
            >
            {(isAddingMemory || completeModal.plannedId === null) ? (
              <div className="overflow-y-auto flex-1 min-h-0">
                <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                  <h3 className="text-xl font-black text-slate-900 uppercase tracking-tighter">New Entry</h3>
                  <button
                    type="button"
                    onClick={() => (completeModal.plannedId === null ? closeCompleteModal() : setIsAddingMemory(false))}
                    className="text-slate-400 hover:text-slate-900"
                    aria-label={completeModal.plannedId === null ? 'Close' : 'Back to scrapbook'}
                  >
                    <X size={20} />
                  </button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Activity Context</label>
                    <input
                      type="text"
                      value={completeActivityTitle}
                      onChange={(e) => setCompleteActivityTitle(e.target.value)}
                      placeholder="What did you do?"
                      className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600"
                    />
                    {completeModal?.plannedId === null && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {filteredActivities.slice(0, 6).map((a: { id: string; title: string }) => (
                          <button
                            key={a.id}
                            type="button"
                            onClick={() => setCompleteActivityTitle(a.title)}
                            className="text-[9px] bg-slate-100 hover:bg-slate-200 text-slate-500 border border-slate-200 px-2 py-1 rounded-sm uppercase font-mono transition-colors"
                          >
                            {a.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <label className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
                      <Users size={12} /> Who was there?
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {otherMembers.map((m) => {
                        const selected = completeParticipants.includes(m.id);
                        return (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() =>
                              setCompleteParticipants((prev) => (selected ? prev.filter((id) => id !== m.id) : [...prev, m.id]))
                            }
                            className={`inline-flex items-center gap-1.5 px-3 py-2 border-2 text-xs font-bold uppercase transition-all ${
                              selected ? 'bg-indigo-600 text-white border-indigo-700' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                            }`}
                          >
                            {selected ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                            {m.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Vibe Check</label>
                    <div className="flex flex-wrap gap-2">
                      {FEELINGS_WITH_EMOJI.map((f) => (
                        <button
                          key={f.value}
                          type="button"
                          onClick={() => setCompleteFeeling((prev) => (prev === f.value ? null : f.value))}
                          className={`px-3 py-2 border-2 text-xs font-bold uppercase flex items-center gap-1.5 transition-all ${
                            completeFeeling === f.value ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                          }`}
                        >
                          <span>{f.icon}</span> {f.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Visuals</label>
                    <div className="grid grid-cols-3 gap-2">
                      {completeFiles.map((_, i) => (
                        <div key={i} className="aspect-square bg-slate-100 border border-slate-200 relative group overflow-hidden rounded">
                          <img src={URL.createObjectURL(completeFiles[i])} alt="" className="w-full h-full object-cover" />
                          <button
                            type="button"
                            onClick={() => {
                              setCompleteFiles((prev) => prev.filter((_, j) => j !== i));
                              setCompleteFileCaptions((prev) => {
                                const next = { ...prev };
                                delete next[i];
                                return next;
                              });
                            }}
                            className="absolute top-1 right-1 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                            aria-label="Remove photo"
                          >
                            <Trash2 size={10} />
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={async () => {
                          const picked = await pickActivityImages();
                          if (picked !== null) {
                            if (picked.length > 0) setCompleteFiles((prev) => [...prev, ...picked]);
                            return;
                          }
                          completeFileInputRef.current?.click();
                        }}
                        className="aspect-square border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 hover:text-indigo-600 hover:border-indigo-400 hover:bg-indigo-50 transition-colors rounded"
                      >
                        <ImageIcon size={20} />
                        <span className="text-[8px] font-bold uppercase mt-1">Add Photo</span>
                      </button>
                    </div>
                    <input
                      ref={completeFileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={async (e) => {
                        const files = Array.from(e.target.files || []);
                        e.target.value = '';
                        if (files.length === 0) return;
                        const withSize = files.filter((f) => {
                          if (f.size === 0) {
                            onAddNotification?.('system', 'Image skipped', 'One or more photos are unavailable (e.g. stored in iCloud). Download them to your device or choose another.');
                            return false;
                          }
                          return true;
                        });
                        if (withSize.length === 0) return;
                        try {
                          const processed = await Promise.all(
                            withSize.map(async (f) => {
                              try {
                                return await processImageForUpload(f);
                              } catch (err) {
                                onAddNotification?.('system', 'Image skipped', err instanceof Error ? err.message : `Could not process "${f.name}".`);
                                return null;
                              }
                            })
                          );
                          const valid = processed.filter((f): f is File => f != null);
                          if (valid.length > 0) setCompleteFiles((prev) => [...prev, ...valid]);
                        } catch (err) {
                          onAddNotification?.('system', 'Error', err instanceof Error ? err.message : 'Could not process images.');
                        }
                      }}
                    />
                    {completeFiles.length > 0 && (
                      <>
                        <p className="mt-1.5 text-[10px] text-slate-500">Tap <strong>Save Raw</strong> below to upload these photos with your memory.</p>
                        <div className="mt-2 space-y-1">
                          {completeFiles.map((_, i) => (
                            <input
                              key={i}
                              type="text"
                              placeholder={`Caption for photo ${i + 1}`}
                              value={completeFileCaptions[i] ?? ''}
                              onChange={(e) => setCompleteFileCaptions((prev) => ({ ...prev, [i]: e.target.value }))}
                              className="w-full border border-slate-200 p-1.5 text-xs bg-slate-50 rounded"
                            />
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Journal Entry</label>
                    <textarea
                      placeholder="Capture the details..."
                      value={completeNotes}
                      onChange={(e) => setCompleteNotes(e.target.value)}
                      className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-medium focus:outline-none focus:border-indigo-600 min-h-[100px]"
                    />
                  </div>
                  {generatedOptionsFromForm && generatedOptionsFromForm.length > 0 ? (
                    <>
                      <div className="flex items-center justify-between bg-indigo-50 p-2 border border-indigo-100 rounded">
                        <span className="text-indigo-700 font-bold text-xs uppercase flex items-center gap-2">
                          <Sparkles size={14} /> AI Layout Preview
                        </span>
                        <button type="button" onClick={() => setGeneratedOptionsFromForm(null)} className="text-[10px] text-slate-500 hover:text-indigo-600 underline font-mono">
                          Discard & Edit
                        </button>
                      </div>
                      <div className="flex gap-2 mb-4 overflow-x-auto no-scrollbar pb-1">
                        {generatedOptionsFromForm.map((opt, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setSelectedOptionIndexFromForm(idx)}
                            className={`flex-1 min-w-[80px] py-2 px-1 text-[9px] font-bold uppercase border-2 transition-all ${
                              selectedOptionIndexFromForm === idx
                                ? 'bg-indigo-600 text-white border-indigo-800 shadow-md'
                                : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                            }`}
                          >
                            {opt.styleName}
                          </button>
                        ))}
                      </div>
                      <div className="w-full max-w-sm mx-auto mb-4">
                        {(() => {
                          const layout = generatedOptionsFromForm[selectedOptionIndexFromForm];
                          const imageUrls =
                            completeFiles.length > 0 ? completeFiles.map((f) => URL.createObjectURL(f)) : [''];
                          return layout ? renderElementScrapbookLayout(layout, imageUrls) : null;
                        })()}
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={runMagicDesignFromForm}
                          disabled={isGeneratingLayoutFromForm}
                          className="flex-1 bg-white hover:bg-slate-50 text-slate-900 border-2 border-slate-200 font-bold uppercase tracking-widest py-2.5 flex items-center justify-center gap-2"
                        >
                          {isGeneratingLayoutFromForm ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />} Regenerate
                        </button>
                        <button
                          type="button"
                          onClick={saveScrapbookFromForm}
                          disabled={saveScrapbookPending}
                          className="flex-[2] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-2.5 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2 border-2 border-indigo-800"
                        >
                          {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save Scrapbook
                        </button>
                      </div>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={handleCompletePlanned}
                      disabled={completeMutation.isPending}
                      className="w-full bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-3 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2"
                    >
                      <Save size={16} /> {completeMutation.isPending ? 'Saving…' : 'Save Raw'}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <>
                <div className="flex justify-between items-center mb-3 shrink-0">
                  <h3 className="font-black text-slate-900 uppercase tracking-tighter text-lg flex items-center gap-2">
                    <BookHeart size={20} className="text-slate-900" /> Scrapbook
                  </h3>
                  <button type="button" onClick={closeCompleteModal} className="text-slate-400 hover:text-slate-900" aria-label="Close">
                    <X size={20} />
                  </button>
                </div>
                <div className="overflow-y-auto flex-1 min-h-0 space-y-3">
                  {(() => {
                    const mem = (memoriesItems as ActivityMemoryItem[]).find((m) => m.id === completeModal.plannedId);
                    if (!mem) {
                      return (
                        <div className="text-center py-12 border-2 border-dashed border-slate-300 bg-slate-50">
                          <Camera size={32} className="mx-auto text-slate-300 mb-2" />
                          <p className="text-xs font-mono text-slate-500 uppercase">No memories archived.</p>
                          <button
                            type="button"
                            onClick={() => setIsAddingMemory(true)}
                            className="mt-3 bg-slate-900 text-white px-4 py-2 text-[10px] font-bold uppercase shadow-lg active:translate-y-0.5"
                          >
                            Log Memory
                          </button>
                        </div>
                      );
                    }
                    const contributions = [...(mem.contributions ?? [])].sort((a, b) => (a.actor_user_id === user?.id ? -1 : b.actor_user_id === user?.id ? 1 : 0));
                    const allEntries = contributions.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name, actor_user_id: c.actor_user_id })));
                    const isShared = contributions.length > 1;
                    return (
                      <>
                        <div className="bg-white border-2 border-slate-200 shadow-[4px_4px_0px_rgba(30,41,59,0.05)]">
                          {isShared && (
                            <div className="bg-slate-50 border-b border-slate-200 px-4 py-2 flex justify-between items-center">
                              <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-indigo-600">
                                <GitMerge size={12} /> Shared Memory
                              </div>
                              <div className="flex -space-x-2">
                                {user?.id && (
                                  <div className="w-6 h-6 rounded-full bg-slate-900 text-white border-2 border-white flex items-center justify-center text-[9px] font-bold shadow-sm">
                                    {user.name?.charAt(0) ?? '?'}
                                  </div>
                                )}
                                {contributions.filter((c) => c.actor_user_id !== user?.id).map((c) => (
                                  <div
                                    key={c.actor_user_id}
                                    className="w-6 h-6 rounded-full bg-indigo-500 text-white border-2 border-white flex items-center justify-center text-[9px] font-bold shadow-sm"
                                  >
                                    {c.actor_name?.charAt(0) ?? '?'}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          <div className="p-4">
                            <div className="flex justify-between items-start mb-3 border-b border-slate-100 pb-2">
                              <div>
                                <h4 className="font-bold text-slate-900 text-sm uppercase">{mem.activity_title}</h4>
                                <span className="text-[9px] font-mono text-slate-400">{mem.completed_at ? new Date(mem.completed_at).toLocaleDateString() : ''}</span>
                              </div>
                              <div className="flex flex-wrap gap-1 justify-end">
                                {(mem.contributions ?? []).filter((c) => c.feeling).map((c, i) => (
                                  <span key={`${c.actor_user_id}-${i}`} className="bg-indigo-50 text-indigo-700 px-2 py-1 text-[9px] font-bold uppercase border border-indigo-200">
                                    {c.feeling}
                                  </span>
                                ))}
                              </div>
                            </div>
                            {allEntries.length > 0 && (
                              <div className="mb-4 overflow-x-auto overflow-y-hidden flex gap-0 snap-x snap-mandatory scroll-smooth -mx-1 px-1" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                                {allEntries.map((e, i) => (
                                  <div key={i} className="flex-shrink-0 w-[85%] max-w-[280px] snap-start snap-always aspect-[4/3] bg-slate-100 border border-slate-200 overflow-hidden relative rounded">
                                    <img src={apiService.getMemoryImageUrl(e.url)} alt={e.caption ?? 'Memory'} className="w-full h-full object-cover" />
                                    {e.caption ? (
                                      <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-2">{e.caption}</div>
                                    ) : null}
                                    <div
                                      className={`absolute bottom-0 right-0 px-2 py-0.5 text-[8px] font-bold uppercase backdrop-blur-sm ${e.actor_user_id === user?.id ? 'bg-slate-900/90 text-white' : 'bg-indigo-600/90 text-white'}`}
                                    >
                                      {e.actor_user_id === user?.id ? 'You' : (e.actorName ?? 'Partner')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                            {contributions.map((c) => {
                              if (!c.notes_text) return null;
                              const isUser = c.actor_user_id === user?.id;
                              return isUser ? (
                                <div key={c.actor_user_id} className="flex gap-3 mb-2">
                                  <div className="w-6 h-6 bg-slate-900 text-white rounded-full flex items-center justify-center text-[9px] shrink-0 font-bold border-2 border-white shadow-sm mt-0.5">
                                    {user?.name?.charAt(0) ?? '?'}
                                  </div>
                                  <div className="bg-slate-50 p-2 rounded-r-lg rounded-bl-lg text-slate-700 text-xs italic font-serif leading-relaxed border border-slate-100 flex-1">
                                    &quot;{c.notes_text}&quot;
                                  </div>
                                </div>
                              ) : (
                                <div key={c.actor_user_id} className="flex gap-3 mt-2 justify-end">
                                  <div className="bg-indigo-50 p-2 rounded-l-lg rounded-br-lg text-indigo-900 text-xs italic font-serif leading-relaxed border border-indigo-100 flex-1 text-right">
                                    &quot;{c.notes_text}&quot;
                                  </div>
                                  <div className="w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-[9px] shrink-0 font-bold border-2 border-white shadow-sm mt-0.5">
                                    {c.actor_name?.charAt(0) ?? '?'}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </>
                    );
                  })()}
                </div>
                <div className="flex justify-end pt-2 border-t border-slate-200 shrink-0">
                  <button type="button" onClick={closeCompleteModal} className="border-2 border-slate-400 px-4 py-2 text-xs font-bold uppercase">
                    Close
                  </button>
                </div>
              </>
            )}
          </div>
        </div>,
        document.body
      )}

      <Modal isOpen={scrapbookDebugModalOpen} onClose={() => setScrapbookDebugModalOpen(false)} title="Scrapbook LLM Debug" size="xl">
        <div className="space-y-4 p-4">
          <div>
            <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Prompt</h4>
            <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-64 whitespace-pre-wrap break-words">
              {scrapbookDebugPrompt ?? '—'}
            </pre>
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Response</h4>
            <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-64 whitespace-pre-wrap break-words">
              {scrapbookDebugResponse ?? '—'}
            </pre>
          </div>
        </div>
      </Modal>
    </>
  );
};
