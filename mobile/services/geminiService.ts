
import { GoogleGenAI, Type, Schema, LiveServerMessage, Modality, FunctionDeclaration } from "@google/genai";
import { ActivityCard, UserProfile } from "../types";
import { createPcmBlob, base64ToUint8Array, decodeAudioData } from "./audioUtils";

const apiKey = process.env.API_KEY || '';
const ai = new GoogleGenAI({ apiKey });

// LiveSession is not exported from the SDK, so we infer it from the return type of connect.
type LiveSession = Awaited<ReturnType<typeof ai.live.connect>>;

// --- Voice Authentication (Simulated) ---
export const verifyVoicePrint = async (audioBase64: string): Promise<boolean> => {
    await new Promise(resolve => setTimeout(resolve, 2000));
    return !!audioBase64; 
};

// --- Therapist Mode ---

export const getTherapistResponse = async (
  history: { role: 'user' | 'model'; text: string }[],
  currentMessage: string,
  user: UserProfile,
  subject: { name: string; relationship: string },
  partnerPerspective?: string
): Promise<string> => {
  const model = "gemini-3-flash-preview";
  
  // Construct profile for the subject based on the passed subject
  const subjectProfile = {
     name: subject.name,
     role: subject.relationship,
     // In a real app, we might fetch specific stats if they are a registered user
     attachmentStyle: 'Unknown', 
     personality: 'Unknown'
  };

  let systemInstruction = `You are an expert Relationship Therapist and Communication Coach trained in **The Gottman Method**, **Attachment Theory**, and **Non-Violent Communication**.
  
  **THE PEOPLE:**
  1. **${user.name}** (User): 
     - Gender: ${user.gender || 'Not specified'}
     - Personality: ${user.personalityType || 'Unknown'}
     - Bio: ${user.personalDescription || 'N/A'}
     - Interests: ${user.interests?.join(', ') || 'N/A'}
     - Attachment Style: ${user.attachmentStyle || 'Unknown'}.
  2. **${subjectProfile.name}** (Target Person): Relationship to user: **${subjectProfile.role}**.

  **YOUR FRAMEWORK:**
  1. **Identify Conflict Patterns**: Look for criticism, defensiveness, contempt, stonewalling, or passive-aggression.
  2. **Analyze Dynamics**: How does ${user.name}'s style interact with this person?
  3. **Provide Antidotes**: Suggest concrete "I feel... I need..." statements or boundary settings suitable for a ${subjectProfile.role}.
  4. **Tone**: Empathetic, objective, coaching-oriented.

  **CRITICAL - STONEWALLING PROTOCOL:**
  If you detect signs of **Stonewalling** (shutting down, withdrawing, feeling overwhelmed, "flooding") in the user's input, you must immediately intervene with physiological self-soothing.
  - Acknowledge the feeling of being overwhelmed/flooded.
  - Explain that they cannot resolve conflict effectively when their heart rate is high.
  - Suggest a brief pause to reset the nervous system.
  - **Explicitly ask**: "Would you like to try a guided breathing exercise?"

  **CRITICAL - CONTEMPT PROTOCOL:**
  If you detect signs of **Contempt** (sarcasm, cynicism, name-calling, eye-rolling, mockery, hostile humor) in the user's input, you must intervene immediately. Contempt is the most destructive horseman.
  - Identify the contempt gently but firmly.
  - Explain that the antidote to contempt is building a culture of **Fondness and Admiration**.
  - **Explicitly ask**: "Would you like to try a specific appreciation exercise?"
  `;

  if (partnerPerspective) {
    systemInstruction += `
    **CRITICAL UPDATE: MEDIATION MODE**
    We have obtained the "Other Side of the Story" from ${subjectProfile.name}.
    
    **${subjectProfile.name}'s Perspective:** "${partnerPerspective}"

    **TASK:**
    1. Validate ${user.name}'s feelings, BUT also explain ${subjectProfile.name}'s reality based on their perspective.
    2. Act as a "Translator": Explain what ${subjectProfile.name} *really* meant vs. what ${user.name} heard.
    3. Propose a specific compromise or "Repair Attempt" that respects BOTH their needs.
    `;
  } else {
    systemInstruction += `
    **MODE: INDIVIDUAL COACHING**
    Help ${user.name} process their feelings regarding ${subjectProfile.name}. 
    If they are complaining about a conflict, guide them to see their own role in the system.
    `;
  }

  const chat = ai.chats.create({
    model,
    config: {
      systemInstruction,
    },
    history: history.map(h => ({ role: h.role, parts: [{ text: h.text }] })),
  });

  const result = await chat.sendMessage({ message: currentMessage });
  return result.text || "I'm listening, please go on.";
};

// --- Activities Mode ---

export const generateActivities = async (
  relationshipStatus: string,
  mood: string
): Promise<ActivityCard[]> => {
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

  try {
    return JSON.parse(result.text || "[]");
  } catch (e) {
    console.error("Failed to parse activities", e);
    return [];
  }
};

// --- Live Coach Mode (Gemini Live API) ---

export interface AnalysisData {
    transcript: string;
    speaker: string;
    sentiment: 'Positive' | 'Neutral' | 'Negative' | 'Hostile';
    horseman: 'None' | 'Criticism' | 'Contempt' | 'Defensiveness' | 'Stonewalling';
}

export interface LiveCoachCallbacks {
  onOpen: () => void;
  onClose: () => void;
  onAudioData: (buffer: AudioBuffer) => void;
  onAnalysis: (data: AnalysisData) => void;
  onError: (error: any) => void;
}

// Tool Definition for the Model to report what it hears/analyzes
const analysisToolDeclaration: FunctionDeclaration = {
    name: "reportAnalysis",
    description: "Reports the transcription and psychological analysis of the latest conversation turn.",
    parameters: {
        type: Type.OBJECT,
        properties: {
            transcript: { type: Type.STRING, description: "The exact words spoken in the last turn." },
            speaker: { type: Type.STRING, description: "The identified speaker name." },
            sentiment: { type: Type.STRING, enum: ['Positive', 'Neutral', 'Negative', 'Hostile'], description: "The emotional tone of the speech." },
            horseman: { type: Type.STRING, enum: ['None', 'Criticism', 'Contempt', 'Defensiveness', 'Stonewalling'], description: "Detected Gottman conflict pattern." }
        },
        required: ["transcript", "speaker", "sentiment", "horseman"]
    }
};

export const connectLiveCoach = async (
    user: UserProfile, 
    callbacks: LiveCoachCallbacks
): Promise<{
  sendAudio: (data: Float32Array) => void;
  disconnect: () => void;
}> => {
  const model = 'gemini-2.5-flash-native-audio-preview-12-2025';
  const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
  const partnerName = user.partnerName || 'Partner';
  
  let sessionResolve: (value: LiveSession) => void;
  const sessionPromise = new Promise<LiveSession>((resolve) => {
    sessionResolve = resolve;
  });

  const session = await ai.live.connect({
    model,
    config: {
      responseModalities: [Modality.AUDIO], // We use AUDIO for interventions, but TOOLS for data stream
      systemInstruction: `You are an advanced **Gottman Method Relationship Coach** observing a live conversation between two partners: **${user.name}** and **${partnerName}**.
      
      **YOUR DUAL ROLE:**
      1. **Silent Analyst (Constant):** For *every* sentence spoken by the users, you MUST call the \`reportAnalysis\` tool.
         - **Transcribe** accurately.
         - **Identify Speakers**: 
             - You will receive a short audio clip at the beginning of this session.
             - **THAT CLIP IS THE VOICE OF ${user.name}**.
             - Use that voice print to distinguish **${user.name}** from **${partnerName}** throughout the conversation.
             - In the \`speaker\` field of the tool, use their ACTUAL NAMES ("${user.name}" or "${partnerName}").
         - **Analyze Tone**: Detect anger, sadness, sarcasm, or warmth.
         - **Detect Horsemen**: Watch for Criticism, Contempt, Defensiveness, or Stonewalling.
      
      2. **Active Coach (Intervention Only):**
         - Generally, remain silent (do not generate audio) and just use the tool.
         - **Generate AUDIO ONLY IF**:
           - You detect **Contempt** (e.g., mockery, name-calling).
           - You detect **Stonewalling** (complete withdrawal).
           - The conflict is escalating rapidly to hostility.
         - If intervening, keep it brief (under 10s), calm, and gentle. Example: "I'm sensing some contempt here. Let's pause and rephrase that with appreciation."`,
      tools: [{ functionDeclarations: [analysisToolDeclaration] }],
    },
    callbacks: {
      onopen: () => {
        // --- VOICE IDENTIFICATION INJECTION ---
        // If we have a voice print, send it immediately to seed the model's context
        if (user.voicePrintData) {
            console.log("Sending Voice Print Data for Identification...");
            sessionPromise.then(s => {
                s.sendRealtimeInput({
                    media: {
                        mimeType: "audio/pcm;rate=16000",
                        data: user.voicePrintData!
                    }
                });
            });
        }
        callbacks.onOpen();
      },
      onmessage: async (msg: LiveServerMessage) => {
        // 1. Handle Tool Calls (The Analysis Stream)
        if (msg.toolCall) {
            for (const fc of msg.toolCall.functionCalls) {
                if (fc.name === 'reportAnalysis') {
                    const analysis = fc.args as unknown as AnalysisData;
                    callbacks.onAnalysis(analysis);
                    
                    // Acknowledge the tool call so the model continues
                    sessionPromise.then(s => s.sendToolResponse({
                        functionResponses: {
                            id: fc.id,
                            name: fc.name,
                            response: { result: "Analysis logged." } 
                        }
                    }));
                }
            }
        }

        // 2. Handle Audio Output (The Coach Interventions)
        const base64Audio = msg.serverContent?.modelTurn?.parts?.[0]?.inlineData?.data;
        if (base64Audio) {
          const uint8 = base64ToUint8Array(base64Audio);
          const audioBuffer = await decodeAudioData(uint8, audioContext);
          callbacks.onAudioData(audioBuffer);
        }
      },
      onclose: () => callbacks.onClose(),
      onerror: (err) => callbacks.onError(err),
    }
  });

  sessionResolve!(session);

  return {
    sendAudio: (float32Data: Float32Array) => {
      const pcmBlob = createPcmBlob(float32Data);
      sessionPromise.then(s => s.sendRealtimeInput({ media: pcmBlob }));
    },
    disconnect: () => {
      sessionPromise.then(s => s.close());
      if (audioContext.state !== 'closed') {
        audioContext.close().catch(console.error);
      }
    }
  };
};
