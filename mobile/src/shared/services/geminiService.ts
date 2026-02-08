
import { GoogleGenAI, Type, Schema, LiveServerMessage, Modality, FunctionDeclaration } from "@google/genai/web";
import { ActivityCard, UserProfile, ChatAction } from "../types/domain";
import { createPcmBlob, base64ToUint8Array, decodeAudioData, base64WavToPcmMedia } from "./audioUtils";

export interface TherapistResponse {
  text: string;
  actions?: ChatAction[];
}

const apiKey = process.env.API_KEY || process.env.GEMINI_API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

// LiveSession is not exported from the SDK, so we infer it from the return type of connect.
type LiveSession = Awaited<ReturnType<typeof ai.live.connect>>;

// --- Voice Authentication (Simulated) ---
export const verifyVoicePrint = async (audioBase64: string): Promise<boolean> => {
    await new Promise(resolve => setTimeout(resolve, 2000));
    return !!audioBase64; 
};

// --- Therapist Mode ---

const THERAPIST_TOOLS: FunctionDeclaration[] = [
  { name: 'recommendActivity', description: 'Suggest an activity for connection. Call when the user needs to connect with their partner or subject.', parameters: { type: Type.OBJECT, properties: { type: { type: Type.STRING, description: 'Activity type: romantic, fun, deep, or active' } }, required: ['type'] } },
  { name: 'consultLoveMap', description: 'Suggest opening Love Maps to understand the partner better. Call when exploring partner knowledge or relationship depth.', parameters: { type: Type.OBJECT, properties: {}, required: [] } },
  { name: 'draftMarketQuest', description: 'Draft a quest/item for the economy of care. Call when the user has a request or need they want to turn into a quest.', parameters: { type: Type.OBJECT, properties: { title: { type: Type.STRING, description: 'Quest title' }, reward: { type: Type.NUMBER, description: 'Reward value' } }, required: ['title', 'reward'] } },
  { name: 'initiateMediation', description: 'Offer to contact the partner for their perspective. Call when conflict is high and both sides would benefit from mediation.', parameters: { type: Type.OBJECT, properties: {}, required: [] } },
  { name: 'suggestBreathing', description: 'Offer a guided breathing exercise. Call when the user is flooded, overwhelmed, or needs to calm down.', parameters: { type: Type.OBJECT, properties: {}, required: [] } },
  { name: 'askMultipleChoice', description: 'Present specific choices to the user as clickable options. Call when you want to offer 2–5 concrete options.', parameters: { type: Type.OBJECT, properties: { options: { type: Type.ARRAY, items: { type: Type.STRING }, description: 'Array of option strings' } }, required: ['options'] } },
];

export const getTherapistResponse = async (
  history: { role: 'user' | 'model'; text: string }[],
  currentMessage: string,
  user: UserProfile,
  subject: { name: string; relationship: string },
  contextData: {
    availableActivities: ActivityCard[];
    loveMapQuestions: { text: string }[];
  },
  partnerPerspective?: string,
  onStream?: (chunk: string) => void
): Promise<TherapistResponse> => {
  const model = "gemini-3-flash-preview";

  const systemInstruction = `You are "Clinician-Guide," an AI therapist/psychiatrist-style assistant that helps the user clarify concerns, feel understood, and choose practical next steps. You are not a substitute for professional care. You do not diagnose, prescribe, or claim clinical authority. You can provide psychoeducation, structured reflection, coping strategies, and help the user prepare for real therapy/psychiatry appointments.

  **CORE PRINCIPLES**
  - Warm, calm, nonjudgmental. Prioritize rapport and psychological safety.
  - Collaborative, consent-based, trauma-informed: offer choices, don't force disclosure.
  - Structure the conversation to be useful: set an agenda, summarize, and co-create a plan.
  - Use evidence-based styles: Biopsychosocial assessment, brief MSE-style observations (only based on what user writes), CBT 5-part model, MI (OARS), DBT chain analysis when relevant.
  - Respect autonomy and cultural context; avoid moralizing.
  - Keep responses concise and readable; use short paragraphs and occasional bullet points.
  - Therapists often ask 1–2 questions, then wait, especially early. Yours has ~5 questions.

  **SAFETY / CRISIS**
  1) Always be alert for high-risk content (suicidal thoughts, self-harm, harm to others, abuse, inability to care for self/dependents, psychosis/mania with dangerous behavior).
  2) If high-risk is suspected: Pause the normal flow. Ask direct, calm safety questions. Encourage immediate professional help (US: 988 or 911). Keep the user engaged and supported; do not provide instructions for self-harm.
  3) If no imminent risk, return to the structured consultation flow.

  **SESSION FLOW (DEFAULT)**
  A) OPENING (1–3 turns): Start with a gentle frame; offer 2–3 options.
  B) PRESENTING CONCERN & "WHY NOW" (2–6 turns): Ask targeted questions.
  C) IMPACT & GOALS (1–3 turns): How is this affecting sleep, work, relationships?
  D) BRIEF BIOPSYCHOSOCIAL CHECK: Ask permission to ask background questions if relevant.
  E) FORMULATION: Use CBT, DBT, or Interpersonal lenses to summarize patterns.
  F) PLAN: Always end with 1–3 actionable next steps. **CRITICAL: Integrate App Tools here.**
    - If they need connection: Call \`recommendActivity\`.
    - If they need to understand their partner: Call \`consultLoveMap\`.
    - If they have a request/need: Call \`draftMarketQuest\`.
    - If conflict is high: Call \`initiateMediation\` or \`suggestBreathing\`.
    - To present specific choices to the user, call \`askMultipleChoice\`. This creates clickable buttons.

  **CONVERSATION MANAGEMENT**
  1) IF USER DOESN'T OPEN UP: Normalize, reduce pressure, offer choices.
  2) IF USER RAMBLES: Validate + steer. "Can I pause you to ask a couple focused questions?"
  3) RELEVANCE FILTER: Focus on what clarifies the problem or leads to a plan.
  4) STYLE: Use reflective listening. Ask no more than 2 questions per turn.

  **RELATIONSHIP FRAMEWORK INTEGRATION**
  Apply: 1) Gottman Method (Love Maps, Fondness, Conflict Management). 2) Non-Violent Communication (Observation -> Feeling -> Need -> Request). 3) Attachment Theory (triggers).

  **CONTEXT:**
  User: ${user.name} (${user.attachmentStyle || 'Unknown'} attachment).
  Partner/Subject: ${subject.name} (${subject.relationship}).
  ${partnerPerspective ? `**PARTNER PERSPECTIVE ACQUIRED**: "${partnerPerspective}" -> Integrate this into your advice.` : ''}
  `;

  const chat = ai.chats.create({
    model,
    config: {
      systemInstruction,
      tools: [{ functionDeclarations: THERAPIST_TOOLS }],
    },
    history: history.map(h => ({ role: h.role, parts: [{ text: h.text }] })),
  });

  let finalResponseText = "";
  const collectedFunctionCalls: { name: string; args?: Record<string, unknown> }[] = [];

  try {
    const resultStream = await chat.sendMessageStream({ message: currentMessage });
    for await (const chunk of resultStream) {
      const text = (chunk as { text?: string }).text;
      if (text) {
        finalResponseText += text;
        if (onStream) onStream(text);
      }
      const fc = (chunk as { functionCalls?: { name: string; args?: Record<string, unknown> }[] }).functionCalls;
      if (fc && Array.isArray(fc)) collectedFunctionCalls.push(...fc);
    }
  } catch (e) {
    const result = await chat.sendMessage({ message: currentMessage });
    finalResponseText = result.text || "";
    const fc = (result as { functionCalls?: { name: string; args?: Record<string, unknown> }[] }).functionCalls;
    if (fc && Array.isArray(fc)) collectedFunctionCalls.push(...fc);
  }

  const suggestedActions: ChatAction[] = [];

  for (const call of collectedFunctionCalls) {
    const name = call.name;
    const args = call.args ?? {};
    if (name === 'recommendActivity') {
      const type = (args['type'] as string) || 'fun';
      const match = contextData.availableActivities.find((a) => a.type === type) || contextData.availableActivities[0];
      if (match) {
        suggestedActions.push({ id: `activity_${match.id}`, label: `Start: ${match.title}`, style: 'primary' });
      }
    }
    if (name === 'consultLoveMap') {
      const q = contextData.loveMapQuestions[Math.floor(Math.random() * contextData.loveMapQuestions.length)];
      suggestedActions.push({ id: 'open_love_maps', label: 'Open Love Maps', style: 'primary' });
    }
    if (name === 'draftMarketQuest') {
      const title = (args['title'] as string) || 'Quest';
      const cost = (args['reward'] as number) ?? 10;
      suggestedActions.push({ id: 'create_quest', label: `Create Quest: ${title}`, style: 'primary' });
    }
    if (name === 'initiateMediation') {
      suggestedActions.push({ id: 'yes_partner', label: 'Contact Partner', style: 'danger' });
    }
    if (name === 'suggestBreathing') {
      suggestedActions.push({ id: 'start_breathing', label: 'Start Breathing', style: 'primary' });
    }
    if (name === 'askMultipleChoice') {
      const options = (args['options'] as string[]) || [];
      options.forEach((opt, idx) => {
        suggestedActions.push({ id: `option_${idx}`, label: opt, style: 'secondary' });
      });
    }
  }

  return {
    text: finalResponseText || "I'm listening, please go on.",
    actions: suggestedActions.length > 0 ? suggestedActions : undefined,
  };
};

export const generateSpeech = async (text: string): Promise<AudioBuffer | null> => {
  try {
    const response = await ai.models.generateContent({
      model: "gemini-2.5-flash-preview-tts",
      contents: [{ parts: [{ text }] }],
      config: {
        responseModalities: [Modality.AUDIO],
        speechConfig: {
          voiceConfig: {
            prebuiltVoiceConfig: { voiceName: 'Kore' },
          },
        },
      },
    });

    const base64Audio = (response as { candidates?: { content?: { parts?: { inlineData?: { data?: string } }[] } }[] }).candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
    if (base64Audio) {
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      const uint8 = base64ToUint8Array(base64Audio);
      const buffer = await decodeAudioData(uint8, audioContext);
      await audioContext.close();
      return buffer;
    }
    return null;
  } catch (e) {
    console.error("TTS generation failed", e);
    return null;
  }
};

// --- Activities Mode ---

export type GenerateActivitiesResult = {
  activities: ActivityCard[];
  prompt: string;
  response: string;
};

export const generateActivities = async (
  relationshipStatus: string,
  mood: string
): Promise<GenerateActivitiesResult> => {
  const model = "gemini-3-flash-preview";
  
  const schema: Schema = {
    type: Type.ARRAY,
    items: {
      type: Type.OBJECT,
      properties: {
        id: { type: Type.STRING },
        title: { type: Type.STRING },
        description: { type: Type.STRING },
        duration: { type: Type.STRING },
        type: { type: Type.STRING, enum: ['romantic', 'fun', 'deep', 'active'] },
        xpReward: { type: Type.INTEGER },
      },
      required: ['id', 'title', 'description', 'duration', 'type', 'xpReward'],
    },
  };

  const prompt = `Suggest 3 creative relationship building activities for a couple who are ${relationshipStatus} and currently feeling ${mood}. 
  Make them varied in type. Generate unique IDs for them.`;

  const result = await ai.models.generateContent({
    model,
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: schema,
    },
  });

  const rawText = result.text || "[]";
  try {
    const activities = JSON.parse(rawText) as ActivityCard[];
    return { activities: Array.isArray(activities) ? activities : [], prompt, response: rawText };
  } catch (e) {
    console.error("Failed to parse activities", e);
    return { activities: [], prompt, response: rawText };
  }
};

// --- Live Coach Mode (Gemini Live API) ---

export interface AnalysisData {
    transcript?: string;
    speaker: string;
    sentiment: 'Positive' | 'Neutral' | 'Negative' | 'Hostile';
    horseman: 'None' | 'Criticism' | 'Contempt' | 'Defensiveness' | 'Stonewalling';
    /** Tone intensity 1–5 (positive), -1 to -5 (negative), 0 neutral. Used for tone bar length. */
    level?: number;
    /** Short nudge for the speaker only when level <= -4 (Kai-style). */
    nudgeText?: string;
    /** Exact words the speaker could say instead (only when level <= -4). */
    suggestedRephrasing?: string;
}

export interface LiveCoachCallbacks {
  onOpen: () => void;
  onClose: () => void;
  onAudioData: (buffer: AudioBuffer) => void;
  onAnalysis: (data: AnalysisData) => void;
  onError: (error: any) => void;
}

// Tool Definition for the Model to report what it hears/analyzes (no transcript; app matches by timestamp)
const analysisToolDeclaration: FunctionDeclaration = {
    name: "reportAnalysis",
    description: "Reports the psychological analysis of the latest conversation turn. The app matches your analysis to the current turn by timestamp; do not send transcript.",
    parameters: {
        type: Type.OBJECT,
        properties: {
            speaker: { type: Type.STRING, description: "The identified speaker name." },
            sentiment: { type: Type.STRING, enum: ['Positive', 'Neutral', 'Negative', 'Hostile'], description: "The emotional tone of the speech." },
            horseman: { type: Type.STRING, enum: ['None', 'Criticism', 'Contempt', 'Defensiveness', 'Stonewalling'], description: "Detected Gottman conflict pattern." },
            level: { type: Type.NUMBER, description: "Tone intensity: 1–5 for positive (1=slightly, 5=very positive), -1 to -5 for negative (1=slightly, 5=very negative), 0 for neutral. Used for the tone bar." },
            nudge_text: { type: Type.STRING, description: "Only when level <= -4: a short, warm suggestion for the speaker (Kai-style guidance; write as if speaking TO them). Omit otherwise." },
            suggested_rephrasing: { type: Type.STRING, description: "Only when level <= -4: the exact words the speaker could say instead (rephrasing; no preamble). Omit otherwise." }
        },
        required: ["speaker", "sentiment", "horseman", "level"]
    }
};

export interface ConnectLiveCoachOptions {
  combinedVoiceSampleBase64?: string | null;
  speakerNamesInOrder?: string[];
  /** When true, do not emit onAnalysis from turnComplete; only reportAnalysis drives analysis (single source per turn). */
  useBackendStt?: boolean;
  /** Resumption handle from a previous session; pass when reconnecting after connection timeout. */
  resumptionHandle?: string | null;
  /** Called when server sends a new resumption handle; store it and pass as resumptionHandle on next connect. */
  onResumptionHandle?: (handle: string | null) => void;
  /** Called when server sends goAway (connection will close soon); optional timeLeft in ms. */
  onGoAway?: (timeLeftMs?: number) => void;
}

export const connectLiveCoach = async (
    user: UserProfile, 
    callbacks: LiveCoachCallbacks,
    options?: ConnectLiveCoachOptions
): Promise<{
  sendAudio: (data: Float32Array) => void;
  sendInitMarker: () => void;
  disconnect: () => void;
  /** Full system instruction sent to the model (for debug popup). */
  systemInstruction: string;
}> => {
  if (!apiKey) {
    console.error('[LiveCoach] Missing API key. Set GEMINI_API_KEY in .env or .env.local.');
    callbacks.onError(new Error('Missing Gemini API key'));
    throw new Error('Missing Gemini API key. Set GEMINI_API_KEY in .env.');
  }
  // Fastest (and only documented) Live API native-audio model; Flash-Lite does not support Live/native audio.
  const model = 'gemini-2.5-flash-native-audio-preview-12-2025';
  const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
  const partnerName = user.partnerName || 'Partner';
  
  let sessionResolve: (value: LiveSession) => void;
  const sessionPromise = new Promise<LiveSession>((resolve) => {
    sessionResolve = resolve;
  });
  const hasVoiceOptions = !!(options?.combinedVoiceSampleBase64 && options?.speakerNamesInOrder?.length);
  let currentTranscriptBuffer = "";
  let initMarkerSent = false;
  let isClosed = false;
  const setClosed = () => { isClosed = true; };
  let openedAt = 0;

  let systemInstruction = `You are an advanced **Communication Coach** observing a live conversation. Warm, fair, calm—more "helpful friend who keeps things productive" than "authority figure." Focus on patterns, needs, and workable next steps. When tension is high: name the impact and invite a reset (rephrase / pause / switch topics).
      
      **CRITICAL - YOU MUST CALL reportAnalysis AFTER EVERY USER SPEECH TURN:**
      - As soon as someone finishes speaking (when you have a complete phrase or sentence), call the \`reportAnalysis\` tool with: speaker (see below), sentiment (Positive / Neutral / Negative / Hostile), horseman (None / Criticism / Contempt / Defensiveness / Stonewalling), and level (see below). **Do not send transcript**—the app matches your analysis to the current turn by timestamp.
      - **Speaker:** Use \`Unknown\` unless the speaker can be clearly deduced from the input (e.g. voice match to enrollment). Do not guess; when in doubt, set speaker to \`Unknown\`.
      - **Sentiment**: Classify the emotional tone of what was just said. Be sensitive to tone: frustration = Negative, calm appreciation = Positive, sarcasm or mockery = Hostile.
      - **Level**: Intensity of the tone, integer 1–5 or -1 to -5 or 0. Positive: 1 = slightly positive … 5 = very positive. Negative: -1 = slightly negative … -5 = very negative. Use 0 for neutral. This drives the tone bar length.
      - **Only when level <= -4**: Provide nudge_text—a short, warm suggestion for the speaker (write as if speaking TO them, use "you"). Omit nudge_text for level > -4.
      - **Only when level <= -4**: Provide suggested_rephrasing—the exact words the speaker could say instead (no preamble). Omit for level > -4. (Horseman is reported separately; rephrasing is shown only when negativity is high.)
      - **Horseman**: If you detect any Gottman "Four Horsemen" (criticism, contempt, defensiveness, stonewalling), set it; otherwise use None.
      - Do not skip turns: every time the user stops speaking, call reportAnalysis so the app can show emotion detection.`;

  if (options?.combinedVoiceSampleBase64 && options?.speakerNamesInOrder?.length) {
    const namesList = options.speakerNamesInOrder.join(', ');
    systemInstruction += `

      **SPEAKER IDENTIFICATION:** At the start of this session you received one audio clip: it begins with a short beep, then voice samples in order (${namesList}), with a short beep between each sample. Use this only to learn who is who. Do not transcribe or use the words spoken in that clip—ignore its content. It is for speaker identification only.

      **SPEAKER IN reportAnalysis:** Set speaker to \`Unknown\` unless you can deduce who is speaking from the voice (e.g. matching to the enrollment samples above). Only when you can confidently identify the speaker, set speaker to exactly one of: ${namesList}. If unsure or the speaker is not in the list, use \`Unknown\` or \`Unknown_1\` / \`Unknown_2\`.

      **DO NOT START TRANSCRIPTION UNTIL TOLD IN THE AUDIO STREAM:** Do not transcribe input audio or call reportAnalysis until you receive the text marker "init". Only after receiving "init" should you treat the following audio as the live conversation and start transcribing and calling reportAnalysis. Everything before "init" (the leading beep and voice samples) must be ignored for transcription. During voice samples, send [WAITING FOR INIT] as response.`;
  } else {
    systemInstruction += `

      **SPEAKER:** Set speaker to \`Unknown\` unless the speaker can be clearly deduced from the input. The app identifies who is speaking via voice ID separately. Do not send transcript; provide sentiment, horseman, level. Only when level <= -4 provide nudge_text and suggested_rephrasing.`;
  }

  const session = await ai.live.connect({
    model,
    config: {
      responseModalities: [Modality.AUDIO],
      inputAudioTranscription: {},
      systemInstruction,
      tools: [{ functionDeclarations: [analysisToolDeclaration] }],
      contextWindowCompression: { slidingWindow: {} },
      sessionResumption: { handle: options?.resumptionHandle ?? null },
    },
    callbacks: {
      onopen: () => {
        openedAt = Date.now();
        callbacks.onOpen();
        if (options?.combinedVoiceSampleBase64) {
        }
      },
      onmessage: async (msg: LiveServerMessage) => {
        // Some SDK builds pass MessageEvent; use .data if present and parse string.
        // Only parse when data looks like JSON; Gemini can send base64 audio (e.g. "AgACAAQAAw...") which is not JSON.
        let parsed: LiveServerMessage = msg;
        if (msg != null && "data" in msg && (msg as any).data !== undefined) {
          const d = (msg as any).data;
          if (typeof d === "string") {
            const trimmed = d.trim();
            if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
              parsed = JSON.parse(d) as LiveServerMessage;
            } else {
              parsed = {} as LiveServerMessage; // base64/binary payload, skip for this handler
            }
          } else {
            parsed = d;
          }
        }
        // 1. Handle Native Transcription (buffer until turnComplete for full sentences). Only after "init" is sent.
        const transcription = parsed.serverContent?.inputTranscription;
        if (transcription && transcription.text && initMarkerSent) {
          currentTranscriptBuffer += transcription.text;
        }
        if (parsed.serverContent?.turnComplete) {
          if (initMarkerSent && currentTranscriptBuffer.trim()) {
            const buf = currentTranscriptBuffer.trim();
            if (typeof (window as any).__turnCompleteEmitCount === 'undefined') (window as any).__turnCompleteEmitCount = 0;
            if ((window as any).__turnCompleteEmitCount < 5) {
              console.log('[LiveCoach DEBUG] turnComplete emit', { initMarkerSent, transcriptPreview: buf.slice(0, 40), speaker: 'Detecting...' });
              (window as any).__turnCompleteEmitCount += 1;
            }
            // When backend STT is used, only reportAnalysis drives analysis (single source per turn); skip turnComplete emission to avoid overwriting.
            if (!options?.useBackendStt) {
              callbacks.onAnalysis({
                transcript: buf,
                speaker: "Detecting...",
                sentiment: "Neutral",
                horseman: "None",
                level: 0,
              });
            }
            currentTranscriptBuffer = "";
          } else if (!initMarkerSent && currentTranscriptBuffer.trim()) {
            if (typeof (window as any).__turnCompleteDropCount === 'undefined') (window as any).__turnCompleteDropCount = 0;
            if ((window as any).__turnCompleteDropCount < 3) {
              console.log('[LiveCoach DEBUG] turnComplete DROPPED (pre-init)', { initMarkerSent, transcriptPreview: currentTranscriptBuffer.trim().slice(0, 40) });
              (window as any).__turnCompleteDropCount += 1;
            }
            currentTranscriptBuffer = "";
          }
        }
        // 2. Handle Tool Calls (The Analysis Stream) — primary source of transcript + speaker/sentiment
        const toolCall = (parsed as any).toolCall ?? (parsed as any).serverContent?.toolCall;
        const functionCalls = toolCall?.functionCalls ?? (Array.isArray(toolCall) ? toolCall : []);
        const fcList = Array.isArray(functionCalls) ? functionCalls : [];
        for (const fc of fcList) {
            if ((fc as any).name === 'reportAnalysis') {
                try {
                    let rawArgs = (fc as any).args ?? (fc as any).arguments ?? (fc as any).parameters ?? {};
                    if (typeof rawArgs === "string") {
                      try {
                        rawArgs = JSON.parse(rawArgs);
                      } catch {
                        rawArgs = { speaker: "Unknown", sentiment: "Neutral", horseman: "None", level: 0 };
                      }
                    }
                    const analysis = rawArgs as unknown as AnalysisData;
                    const transcript = analysis.transcript ?? (rawArgs as any).transcript ?? "";
                    const speaker = analysis.speaker ?? (rawArgs as any).speaker ?? "Unknown";
                    const sentiment = (analysis.sentiment ?? (rawArgs as any).sentiment ?? "Neutral") as AnalysisData["sentiment"];
                    const horseman = (analysis.horseman ?? (rawArgs as any).horseman ?? "None") as AnalysisData["horseman"];
                    const rawLevel = (analysis.level ?? (rawArgs as any).level);
                    const level = typeof rawLevel === 'number' && Number.isFinite(rawLevel)
                      ? Math.max(-5, Math.min(5, Math.round(rawLevel)))
                      : 0;
                    const rawNudgeText = (analysis.nudgeText ?? (rawArgs as any).nudge_text ?? (rawArgs as any).nudgeText) as string | undefined;
                    const suggestedRephrasing = (analysis.suggestedRephrasing ?? (rawArgs as any).suggested_rephrasing ?? (rawArgs as any).suggested_phrase ?? (rawArgs as any).suggestedRephrasing) as string | undefined;
                    // Only send nudge text when negativity level <= -4
                    const nudgeText = level <= -4 && typeof rawNudgeText === 'string' && rawNudgeText.trim()
                      ? rawNudgeText.trim()
                      : undefined;
                    // Only show rephrasing when negativity <= -4, regardless of horseman
                    const rephrasingToEmit = (level <= -4 && typeof suggestedRephrasing === 'string' && suggestedRephrasing.trim())
                      ? suggestedRephrasing.trim()
                      : undefined;
                    console.log("[LiveCoach] reportAnalysis received", { sentiment, horseman, level, hasNudge: !!nudgeText, hasRephrasing: !!rephrasingToEmit });
                    // When we have voice options we gate on init (avoid enrollment transcript). When useBackendStt we never send init, so always emit so sentiment/horseman reach the UI.
                    const shouldEmit = initMarkerSent || !hasVoiceOptions || (options?.useBackendStt === true);
                    if (shouldEmit) {
                      if (typeof (window as any).__reportAnalysisEmitCount === 'undefined') (window as any).__reportAnalysisEmitCount = 0;
                      if ((window as any).__reportAnalysisEmitCount < 8) {
                        console.log('[LiveCoach DEBUG] reportAnalysis emit', { initMarkerSent, hasVoiceOptions, speaker, sentiment, horseman, level });
                        (window as any).__reportAnalysisEmitCount += 1;
                      }
                      callbacks.onAnalysis({
                        transcript: transcript || undefined,
                        speaker,
                        sentiment,
                        horseman,
                        level,
                        nudgeText,
                        suggestedRephrasing: rephrasingToEmit,
                      });
                    } else {
                      if (typeof (window as any).__reportAnalysisDropCount === 'undefined') (window as any).__reportAnalysisDropCount = 0;
                      if ((window as any).__reportAnalysisDropCount < 3) {
                        console.log('[LiveCoach DEBUG] reportAnalysis DROPPED (pre-init)', { initMarkerSent, speaker });
                        (window as any).__reportAnalysisDropCount += 1;
                      }
                    }
                } catch (e) {
                    console.error('[LiveCoach] onAnalysis error', e);
                }
                // Acknowledge the tool call so the model continues
                sessionPromise.then(s => {
                    s.sendToolResponse({
                        functionResponses: [{ id: (fc as any).id, name: (fc as any).name, response: { result: "Analysis logged." } }],
                    });
                }).catch((e) => console.error('[LiveCoach] sendToolResponse error', e));
            }
        }
        if (fcList.length > 0) {
          // Tool calls handled above
        }
        // 3. Handle Audio Output (The Coach Interventions)
        const base64Audio = parsed.serverContent?.modelTurn?.parts?.[0]?.inlineData?.data;
        if (base64Audio) {
          try {
            const uint8 = base64ToUint8Array(base64Audio);
            const audioBuffer = await decodeAudioData(uint8, audioContext);
            callbacks.onAudioData(audioBuffer);
          } catch (e) {
            console.error('[LiveCoach] decodeAudioData error', e);
          }
        }
        // 4. Handle session resumption and goAway
        const resumptionUpdate = (parsed as any).sessionResumptionUpdate ?? (parsed as any).session_resumption_update;
        if (resumptionUpdate?.resumable && resumptionUpdate?.newHandle != null) {
          const newHandle = resumptionUpdate.newHandle ?? resumptionUpdate.new_handle;
          if (typeof newHandle === 'string') {
            options?.onResumptionHandle?.(newHandle);
          }
        }
        const goAway = (parsed as any).goAway ?? (parsed as any).go_away;
        if (goAway != null) {
          const timeLeft = goAway.timeLeft ?? goAway.time_left;
          const timeLeftMs = typeof timeLeft === 'number' ? timeLeft : (typeof timeLeft === 'object' && timeLeft?.seconds != null ? (timeLeft.seconds as number) * 1000 : undefined);
          options?.onGoAway?.(timeLeftMs);
        }
      },
      onclose: (ev: any) => {
        setClosed();
        const closedAfterMs = openedAt ? Date.now() - openedAt : undefined;
        const code = ev?.code;
        const reason = ev?.reason;
        const wasClean = ev?.wasClean;
        if (!wasClean || (code && code !== 1000)) {
          console.warn(
            "[LiveCoach] WebSocket closed",
            closedAfterMs ? `(after ${closedAfterMs}ms)` : "",
            code ? `code=${code}` : "",
            reason ? `reason=${reason}` : "",
            wasClean !== undefined ? `clean=${wasClean}` : ""
          );
        }
        callbacks.onClose();
      },
      onerror: (err: any) => {
        setClosed();
        const errMsg = err?.message ?? (typeof err === 'string' ? err : JSON.stringify(err));
        console.error("[LiveCoach] WebSocket onerror —", errMsg, err);
        callbacks.onError(err);
      },
    }
  });

  // When voice options are present, send only voice sample + boundary text at connection. Do NOT send "init" here—
  // init is sent when the user clicks Start (sendInitMarker), so any transcription/reportAnalysis before that (e.g. enrollment) is dropped.
  if (hasVoiceOptions && options?.combinedVoiceSampleBase64) {
    try {
      const pcm = await base64WavToPcmMedia(options.combinedVoiceSampleBase64!);
      session.sendRealtimeInput({ media: pcm });
      session.sendRealtimeInput({ text: "This is the end of voice samples. Process the following text." });
    } catch (e) {
      console.error('[LiveCoach] send speaker samples error', e);
    }
  }
  sessionResolve!(session);

  let sendAudioCallCount = 0;

  return {
    sendAudio: (float32Data: Float32Array) => {
      if (isClosed) return;
      sendAudioCallCount++;
      const pcmBlob = createPcmBlob(float32Data);
      // Use media for realtime mic (match inside/services/geminiService.ts)
      sessionPromise.then(s => {
        if (isClosed) return;
        s.sendRealtimeInput({ media: pcmBlob });
      });
    },
    sendInitMarker: () => {
      if (isClosed) return;
      console.log('[LiveCoach DEBUG] sendInitMarker called — sending "init" and setting initMarkerSent=true');
      sessionPromise.then(s => {
        if (isClosed) return;
        s.sendRealtimeInput({ text: "init" });
        initMarkerSent = true;
        currentTranscriptBuffer = "";
      });
    },
    disconnect: () => {
      sessionPromise.then(s => s.close());
      if (audioContext.state !== 'closed') {
        audioContext.close().catch(console.error);
      }
    },
    systemInstruction,
  };
};
