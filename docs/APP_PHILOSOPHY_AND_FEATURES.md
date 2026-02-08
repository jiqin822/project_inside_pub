# Project Inside: Philosophy & Main Functionalities

## Theoretical foundation: The Gottman Method (Sound Relationship House)

Project Inside is designed around the **Gottman Method** and the **Sound Relationship House**: the idea that we can build stronger relationships by working on specific, research-backed skills—and that harmful patterns can be corrected when we name them and replace them with better ones.

### The Four Horsemen and their antidotes

If we can identify **criticism, contempt, defensiveness, and stonewalling**, we can correct them:

| Horseman        | Antidote                                      |
|-----------------|-----------------------------------------------|
| **Criticism**   | **Gentle startup** — ask for what you need without blame. |
| **Contempt**    | **Build appreciation** — express fondness and admiration; aim for a positive-to-negative ratio of at least 5:1. |
| **Defensiveness** | **Take responsibility** — even partial (“I see how that came across”). |
| **Stonewalling** | **Physiological self-soothing** — pause, breathe, calm the body before re-engaging. |

The app helps users **recognize** these patterns (e.g. Live Coach) and **practice** the antidotes through structure and daily actions.

### The Sound Relationship House: 7 levels + foundation

Building the relationship is analogous to **building a house**: start with the foundation, then add each floor. Coaching each person to build the house and **integrate practice into daily life** is central. Below, each level is linked to the app features that support it.

| Level | Sound Relationship House | What we practice | App support |
|-------|---------------------------|------------------|-------------|
| **1** | **Love Maps** | Know each other’s inner world: stress, dreams, fears, values—and treat it as **dynamic** (e.g. “What’s stressing you?” “What are you most excited about?”). | **Love Maps** (prompts, tiers, answers; Insider Compass uses this for portraits and personalization). |
| **2** | **Fondness & admiration** | Express appreciation regularly. “I really appreciate you…” Negative vs positive ratio: aim for **at least 1:5**. | **Hearts & emotions**, **Send emotion**, gratitude-focused **Activities**, **Rewards/economy** (offers and thank-yous). |
| **3** | **Turn toward instead of away** | When your partner bids for attention, **look up and respond**—briefly but warmly. | **Real-time connection**: emoji pokes, hearts, emotions; **Reaction menu**; **Notifications** (so bids are visible and can be acknowledged). |
| **4** | **Positive perspective** | Don’t assume your partner is hostile. **Assume good intentions.** | **Therapist** (reframing, perspective); **Live Coach** (nudges toward assuming intent); **Calm-down** (reset before interpreting). |
| **5** | **Manage conflict** | Gentle startup; distinguish **solvable vs perpetual** problems; **accept influence**; **timely repair**. | **Live Coach** (Four Horsemen + antidotes, escalation detection, repair prompts); **Therapist** (repair scripts, next steps); **Calm-down** (self-soothing when stonewalling risk is high). |
| **6** | **Make life dreams come true** | Support each other’s **life dreams and core values**. Behind many conflicts are unspoken dreams. | **Love Maps** (dreams, values, history); **Therapist** (goals, dreams in context); **Activities** (shared meaning and support). |
| **7** | **Create shared meaning** | Build “**our** culture”—rituals, symbols, shared narrative. | **Love Maps** (shared history, “what’s fun for us”); **Activities** (rituals, connection recipes); **Economy** (shared tokens, rituals of earn/spend). |
| **Foundation** | **Commitment & trust** | Use “we” language; **protect the relationship** in public and in private. | **Onboarding** (relationship type, loved ones); **Profile** (who we are together); **Privacy** (what we share); product copy and prompts that use “we” where appropriate. |

---

## Philosophy (how we talk about it)

### Closeness over "right"

Project Inside was born from the realization that in close relationships, **winning an argument is the wrong goal**. When we get stuck on who’s right, we drift apart. **Closeness**—feeling understood, connected, and safe with the people who matter most—is what we’re actually after. That aligns with the Sound Relationship House: we build the house **together**, and we correct the Four Horsemen so that conflict doesn’t erode the foundation. The app supports **empathy, perspective, and understanding** instead of scoring points.

### Heart distance

Physical distance is one thing; **heart distance** is another. You can be in the same room and feel far apart, or miles away and still close. Shrinking heart distance is what “turning toward,” fondness and admiration, and shared meaning are about. Project Inside aims to reduce heart distance through **small, consistent actions**: sending love and emotions, responding to bids in the moment, and doing things that say “I see you” so your most important relationships feel closer regardless of location.

### Getting "inside"

The name **Inside** means getting **inside** your most important people—and letting them get inside you—through:

- **Communication** — How you talk, listen, and show up in real time (e.g. Live Coach, reactions, emotions). *Supports: turn toward, positive perspective, conflict management.*
- **Knowing each other** — Love Maps, personality (e.g. MBTI), attachment, and relationship context so the product can support you in a way that fits your dynamic. *Supports: Love Maps (level 1), life dreams (level 6), shared meaning (level 7).*
- **Daily actions** — Hearts, emotions, emoji pokes, rewards, and activities that turn intention into small, repeatable steps. *Supports: fondness & admiration (level 2), turn toward (level 3).*

The product is not another messaging app. It’s a place to **nurture** those relationships with structure (e.g. economy, activities, coaching) and light touch (e.g. watch taps, in-app tags, nudges)—**one floor of the Sound Relationship House at a time**.

---

## Main Functionalities (with Gottman mapping)

### 1. Identity & onboarding
- **Auth** — Login/signup; JWT-backed session.
- **Onboarding wizard** — Name, avatar, gender, personal description, interests.
- **Personality** — MBTI-style sliders (E/I, S/N, T/F, J/P); optional “prefer not to say.”
- **Attachment** — Optional attachment style (secure, anxious, avoidant, disorganized) and stats.
- **Loved ones** — Invite partners/family/friends by email; define relationship type (e.g. Partner, Child); pending invites until they join.
- **Voice print** — Optional voice enrollment for Live Coach speaker identification.
- **Biometric sync** — Optional biometric (e.g. Face ID) for quick access.

*Supports: **Foundation** (commitment, “we,” defining who is in the relationship).*

### 2. Dashboard & "Active Units"
- **Dashboard home** — Central hub: loved ones tray + floor plan.
- **Active Units tray** — Row of avatars for each loved one (and “add unit”). Shows:
  - **Emoji tags** — When someone sends you an emoji poke (real-time).
  - **Emotion tags** — When someone sends you an emotion (heart badge for a short time).
- **Floor plan** — Visual map of “rooms” that open into different app modes (Therapist, Activities, Rewards, Love Maps, Profile, Live Coach).
- **Reaction menu** — Long-press a loved one’s icon to open a reaction strip:
  - **Send emotion** — Sends an emotion notification (watch full-screen 5s / in-app tag / push).
  - **Emoji reactions** — Love, Happy, Kiss, Hug, Thumbs Up, etc., sent as real-time pokes.

*Supports: **Turn toward** (level 3) — bids and responses visible; **Fondness & admiration** (level 2) — quick ways to express care.*

### 3. Hearts & emotions
- **Hearts** — One-tap (or watch long-press) “heart” to a loved one; creates an in-app notification for them; relationship-gated.
- **Emotions** — First-class notification type (e.g. “love”, “hug”):
  - **Send** — From phone (reaction menu “Send emotion”) or from watch (single tap on a contact).
  - **Receive** — On watch: full-screen for 5 seconds (sender name + emotion kind); in app: small heart tag on that person’s icon; or as a phone push if watch isn’t used.
- **Backend** — `POST /v1/notifications/send-heart` and `POST /v1/notifications/send-emotion`; WebSocket pushes `notification.new` with optional `sender_id`, `sender_name`, `emotion_kind` for emotion type.

*Supports: **Fondness & admiration** (level 2); **Turn toward** (level 3) — receiving and acknowledging bids.*

### 4. Real-time connection (WebSocket)
- **Emoji pokes** — User A sends an emoji to User B in a relationship; B sees it in real time (Active Units tag, optional watch full-screen or push).
- **Notification.new** — When a notification is created (e.g. heart, emotion), the backend pushes it over the same WebSocket so the client can update UI, send to watch, or show a push.
- **Connection** — `/v1/interaction/notifications?token=...`; client keeps session and receives pokes + notification events.

*Supports: **Turn toward** (level 3) — low-friction bids and real-time response.*

### 5. Live Coach
- **Purpose** — Support real-time conversations with empathy and perspective (e.g. during conflict or important talks), without acting as a “judge.”
- **Flow** — User enters Live Coach; optional voice-print gate; starts a session; device captures audio.
- **Backend STT** — Speech-to-text with speaker identification (voice profiles) so the coach knows “who said what.”
- **AI analysis** — Sentiment and “Four Horsemen”–style signals (criticism, contempt, defensiveness, stonewalling) to surface escalation risk.
- **UI** — Transcript with speaker labels; sentiment indicator; optional horseman highlight; coaching annotations when things get heated.
- **Escalation** — When tension is detected, the coach can suggest calming down (e.g. breathing), and optionally send a nudge to the user’s watch or show an in-app notification.

*Supports: **Four Horsemen → antidotes** (gentle startup, appreciation, responsibility, self-soothing); **Conflict management** (level 5); **Positive perspective** (level 4).*

### 6. Therapist (Lounge)
- **Purpose** — Reflective, private space for relationship and self-reflection (not live conversation).
- **AI chat** — User talks to an AI “therapist” with relationship context (e.g. partner name, goals); responses in markdown.
- **Calm-down** — Breathing / self-soothing overlay (e.g. inhale/hold/exhale) to reset before or after hard conversations.
- **Actions** — Chat can suggest actions (e.g. “Talk to your partner”); user can trigger in-app notifications from here.

*Supports: **Stonewalling antidote** (physiological self-soothing via calm-down); **Positive perspective** (level 4); **Life dreams** (level 6); **Conflict repair** (level 5).*

### 7. Activities
- **Activity cards** — Curated activities (e.g. date ideas, deep questions, light fun) with title, description, duration, type (romantic, fun, deep, active), and XP. Personalized by Insider Compass (portraits, memories, recent history).
- **Purpose** — Give couples/families concrete ways to spend time together and reduce heart distance through shared experiences.

*Supports: **Fondness & admiration** (level 2); **Shared meaning** (level 7); **Life dreams** (level 6); **Turn toward** (level 3) — doing something together.*

### 8. Love Maps
- **Purpose** — Map and explore the relationship (e.g. values, history, preferences, stress, dreams, fears) so the app and the user can “know” the relationship better. Treated as **dynamic** (e.g. “What’s stressing you?” “What are you most excited about?”).
- **Implementation** — Dedicated Love Maps screen; prompts by tier (Basics, Dreams, Stress, History, Intimacy); answers feed Insider Compass for portraits and personalization.

*Supports: **Love Maps** (level 1); **Life dreams** (level 6); **Shared meaning** (level 7).*

### 9. Rewards & economy
- **Per-relationship economy** — Each user can define a currency (e.g. Love Tokens, Hearts) for their relationship; the other person earns and spends it.
- **Market** — Items with cost, icon, type (service/product/quest), category (earn vs spend). “Earn” = bounties/requests (do something, get paid); “Spend” = rewards/offers (pay to give something).
- **Vault** — User’s purchased items (to redeem) and their own offers/requests; partner can accept bounties or approve completed tasks.
- **Transactions** — States like purchased, redeemed, accepted, pending_approval, approved, canceled so both sides see progress.

*Supports: **Fondness & admiration** (level 2) — “I appreciate you” via offers/quests; **Shared meaning** (level 7) — “our” economy and rituals.*

### 10. Profile & preferences
- **Personal profile** — View and edit name, avatar, description, interests, personality, attachment, relationship status; optional voice print.
- **Preferences** — Notifications, haptic feedback, privacy mode, share data; optional STT language and debug (e.g. speaker labels, scores) for Live Coach.
- **Economy settings** — User’s own currency name/symbol for others to earn in relationship with them.

*Supports: **Foundation** (commitment, trust, how we show up in the relationship).*

### 11. Notifications
- **Notification center** — Inbox of notifications (message, alert, reward, system, emotion); filter by type; unread count; mark read / mark all read.
- **Types** — From backend: created via API or send-heart/send-emotion; from app: e.g. Live Coach escalation, Therapist suggestions.
- **Delivery** — Stored in backend; pushed in real time via WebSocket; displayed in app and optionally as device push or watch experience.

*Supports: **Turn toward** (level 3) — not missing bids; **Fondness & admiration** (level 2) — receiving appreciation.*

### 12. Apple Watch (iOS)
- **Loved ones grid** — Synced list of loved ones; tap = send emotion; long-press = send heart.
- **Receive** — When phone gets an emotion, it can forward to watch; watch shows full-screen overlay (sender + emotion kind) for 5 seconds; tap to dismiss.
- **Bridge** — Capacitor plugin (WatchNudge) using WatchConnectivity; app registers listeners for `watchSendHeart` and `watchSendEmotion` and calls backend; plugin sends emotion/emoji payloads to watch for display.

*Supports: **Turn toward** (level 3); **Fondness & admiration** (level 2) — quick, visible bids and receipt.*

---

## Summary

**Theory:** The Gottman Method (Sound Relationship House): correct the Four Horsemen with their antidotes, and build the relationship floor by floor (Love Maps → fondness & admiration → turn toward → positive perspective → manage conflict → life dreams → shared meaning) on a foundation of commitment and trust.

**Philosophy:** Closeness over “right”; shrink heart distance; get “inside” your most important people through communication, knowing each other, and daily actions—aligned with building the Sound Relationship House.

**Main functionalities:** Onboarding (profile, personality, loved ones, voice); dashboard with Active Units and floor plan; hearts and emotions (phone + watch, tag / full-screen / push); real-time pokes and notifications; Live Coach (Four Horsemen + antidotes, conflict support); Therapist (reflection + calm-down); Activities (personalized); Love Maps (dynamic knowing); per-relationship Rewards/economy; Profile and preferences; Notification center; Apple Watch send/receive and full-screen emotion.
