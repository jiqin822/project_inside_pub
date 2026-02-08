## Project Inside

### Inspiration
I built **Project Inside** to solve a problem I faced in my own relationship: the cycle of arguing to be *right* instead of staying close.

After watching a reality show where couples repaired their bonds through guided mini-games and objective observation, I realized **structure + perspective** are the keys to connection. Project Inside is my attempt to **democratize couples therapy**—taking proven communication principles and gamified interaction, and embedding them into daily life to make love easier and more resilient.

---

### What it does
Project Inside weaves together **conversation analysis**, live and chat-based coaching, **personalized activity recommendations**, a **relational economy**, and shared memories to help partners **understand themselves and each other**, build better habits, overcome challenges in real time, and celebrate their progress. All through an personalized AI agent called **Kai**.

#### 1) Dialogue Deck (Live Coach)
A real-time **communication guardrail**.
- Uses live audio analysis to detect conflict patterns (e.g., the “Four Horsemen”)
- Use "conversation barometer" to record the progress of the conversation
- Provides immediate, private nudges to help partners de-escalate and listen. (Wearable nudging WIP.)

#### 2) "Conversation" Mode
An AI-powered **communication space** that offers individuals, couples, and families a safe environment to discuss and resolve challenges. Guided by an AI assistant, it helps steer conversations toward healthy, constructive outcomes—preventing escalation and fostering understanding.

#### 3) Smart Activities & Memory Building
Personalized “do something together” actions—not generic date ideas.
- A personalized AI agent recommends tailored activities (e.g., *Deep Dive Walk*, *Nostalgia Night*)
- Completing activities and build **Memories**: digital artifacts that track shared growth and history

#### 4) Relational Economy
A playful token-based economy to reduce friction in day-to-day life.

- Partners can **earn/spend** love currency
- Post **Bounties** (requests like washing dishes) and **Vouchers** (gifts like a massage)
- Turns division of labor into a lightweight exchange of care and value

#### 5) Love Maps
A gamified discovery layer that also powers personalization.

- Trivia + deep questions about each other
- Users earn points *and* feed the system data to improve recommendations (activities, gifts, coaching)

---

### How we built it
> Note: The modules below are the core product pillars and how they work together.

#### Core modes and modules
- **Live Communication Coach Mode**
  - Real-time guardrails during live conversations (not a judge)
  - Uses realtime language agnostic speech-to-text + speaker ID to track “who said what”
  - Detects escalation signals (e.g., Four Horsemen) and nudges de-escalation
  - Offers quick reframe or calm-down prompts to keep connection first
  - Nudges from wearable. (WIP)

- **"Therapist" Mode (The Mediator)**
  - Guides couples/families through structured problem-solving
  - Suggests rephrasing (“try saying… instead of…”) and coaching steps (“validate her feeling first”)
  - Also supports private venting + emotional processing before re-engagement and during engagement.

- **Personalized Activities**
  - Uses understanding of the couple’s issues + interests
  - Generates low-pressure activities that help them work through specific dynamics together

- **Memory Boards (Scrapbook)**
  - Takes completed activity or any ad hoc activity and generates a scrapbook out of the pictures and text memories you provide.
  - Creates a visual history of the relationship over time

- **Relational Economy**
  - Offers/Requests marketplace for daily micro-interactions
  - Converts chores and care into a playful “economy of connection”

- **[WIP] Love Maps (The Discovery Layer)**
  - Gamified questions that deepen understanding
  - Builds the foundational data layer: preferences, history, values, patterns

---

### Challenges we ran into

#### 1) The latency trade-off
We initially built real-time coaching with **Gemini Live Audio** for end-to-end analysis. As sessions grew longer, the context window created significant lag.

**Pivot:** Backend **ASR + Diarization + speaker ID + text analysis** architecture

- Slightly slower per round in some cases
- But enables parallelism, quicker streaming transcripts, and better responsiveness in long sessions

#### 2) The “vibe” problem
“Relationship reasoning” is not logical reasoning. Early prompts were **hypersensitive**, flagging normal directness as hostility.

**Fix:** prompt iteration focused on:

- Context of close relationships
- Distinguishing “upfront” from “toxic”
- Reducing false positives while still catching real escalation signals

#### 3) AI-generated UI consistency
AI tools accelerated frontend work, but screens generated in isolation drifted in style.

**Fix:** a manual “unification pass”

- Standardized layout patterns
- Consistent spacing/typography
- Cohesive visual language across screens

---

### Accomplishments we’re proud of

#### 1) The “Insider” Personalization Engine
We built a central brain that learns from *every* interaction:
- Therapist Mode reflections
- Love Maps answers
- Activities completed
- Marketplace offers/requests

All of it feeds a unified profile so coaching tips and recommendations feel like they come from someone who truly knows the user, the couple, the family.

#### 2) Operationalizing empathy
We translated abstract psychological concepts into real-time product behavior—effectively putting a “therapist and a family assistant in your pocket” that knows you and knows when to step in.

---

### What we learned

#### 1) Action speaks louder than knowledge
Knowing facts (Love Maps) is useful, but users felt closest when they **did things together**. This drove a shift toward:

- Activities
- Marketplace transactions
- Shared experiences that compound over time

#### 2) Reactiveness is emotional currency
In real-time conversations, silence feels like disconnection. Perceived responsiveness mattered more than raw speed.

**Design takeaway:** show partials immediately
- interim transcripts
- “thinking” states
- progressive updates

Even if deep analysis takes time, immediate feedback keeps trust and flow.

---

### What’s next
- **Finish the data loop:** complete Love Maps so it feeds richer data into every engine
- **Polish the brain:** refine User Portrait + Personalization so recommendations feel more intuitive and “magical”
- **Add wearable intervention:** in LiveCoach mode, when conflict gets too heated, send wearable haptic to enforce calm down and suggest that the users step back and take a break.
- **Fine-tune for relationships:** train a specialized model for relationship reasoning (nuance, sarcasm, long-term couple shorthand)
