# Project Inside - Comprehensive Project Description

## Project Overview

**Project Inside** is a comprehensive relationship coaching and communication platform that combines AI-powered real-time conversation analysis, gamified relationship building, and a relational economy system. The platform helps couples and loved ones improve their communication, deepen their understanding of each other, and build stronger relationships through interactive tools, personalized coaching, and meaningful interactions.

### Core Value Proposition

Project Inside transforms relationship improvement into an engaging, data-driven experience by:
- Providing real-time communication coaching during conversations
- Gamifying relationship knowledge through trivia-style "Love Maps"
- Creating a relational economy where partners can earn and spend personalized currencies
- Offering AI-powered insights and therapeutic guidance
- Building a comprehensive knowledge graph of each partner's preferences, needs, and personality

---

## Functional Modules

### 1. Authentication & Onboarding Module

**Purpose**: User registration, authentication, and initial profile setup

**Features**:
- Email/password authentication with JWT tokens
- Invite-based relationship creation with email invitations
- Multi-step onboarding process:
  - **Step 1: Identity Configuration** - Name, gender, profile picture selection
  - **Step 2: Personality Assessment** - MBTI sliders (E/I, S/N, T/F, J/P) with "Prefer not to say" option
  - **Step 3: Voice Print Setup** - Biometric voice enrollment for speaker identification
  - **Step 4: Loved Ones Setup** - Add relationships via email, with invite flow for non-registered users
- Profile picture selection from avatar library (MBTI-based avatars)
- Personal description and interests collection

**User Flow**:
1. User signs up or logs in
2. If new user, completes onboarding steps
3. Adds loved ones (partners, family, friends)
4. Sets up voice print for Dialogue Deck access
5. Transitions to main dashboard

---

### 2. Dashboard Module

**Purpose**: Central hub displaying all relationships and quick access to features

**Features**:
- **Active Units Tray**: Visual representation of all loved ones with:
  - Profile pictures
  - Relationship type labels
  - Love currency balances
  - Real-time emoji reactions (sent/received)
  - Pending relationship indicators
- **Room Navigation**: Access to 6 specialized "rooms":
  1. **Activities Mode** - Suggested activities and date ideas
  2. **Therapist Mode** - AI-powered conflict resolution and mediation
  3. **Love Maps Mode** - Gamified knowledge graph trivia
  4. **Rewards Mode** - Relational economy marketplace
  5. **Dialogue Deck** - Real-time conversation coaching
  6. **Personal Profile** - User settings and profile management
- **Quick Actions**: 
  - Add new loved ones
  - Send emoji reactions (poke/nudge system)
  - View notifications
  - Access personal profile

**User Experience**:
- Floor plan metaphor with rooms as interactive spaces
- Real-time updates via WebSocket for emoji reactions
- Visual indicators for pending relationships
- Smooth transitions between modes

---

### 3. Dialogue Deck (Live Coach Mode)

**Purpose**: Real-time conversation analysis and coaching during live conversations

**Features**:
- **Real-time Audio Processing**:
  - Continuous microphone input capture
  - Speaker identification via voice prints
  - Automatic Speech Recognition (ASR) transcription
  - Sentiment analysis
  - "Four Horsemen" detection (criticism, contempt, defensiveness, stonewalling)
- **Live Feedback**:
  - Visual transcript with speaker labels and colors
  - Real-time sentiment indicators
  - Alert notifications when communication patterns are detected
  - Coaching nudges and suggestions
- **Voice Print Integration**:
  - Requires voice print setup before access
  - Uses enrolled voice profiles for speaker identification
  - Supports multiple speakers in conversation

**User Flow**:
1. User enters Dialogue Deck
2. System checks for voice print (prompts setup if missing)
3. User starts conversation
4. System analyzes audio in real-time
5. Displays transcript, sentiment, and alerts
6. Provides coaching feedback

**Technical Implementation**:
- WebSocket connection to Gemini API for streaming audio
- AudioContext for audio processing
- Real-time transcription and analysis
- Visual feedback dashboard

---

### 4. Love Maps Module

**Purpose**: Gamified knowledge graph system for understanding partners

**Features**:
- **My Specs Mode**: 
  - Users answer questions about themselves (dreams, stress triggers, preferences, etc.)
  - Questions organized by categories (Dreams, Stress, History, Intimacy, etc.)
  - Difficulty tiers (1-5) from basics to deep/esoteric
  - Edit functionality for each answer
- **Quiz Mode**:
  - Generate trivia quizzes about partner's specs
  - Multiple choice questions with AI-generated distractors
  - XP and star rating system (3 stars = 100%, 2 = 70-99%, 1 = 50-69%, 0 = <50%)
  - Level progression (6 tiers total)
  - Unlock mechanism (requires ≥3 specs per tier)
- **Progress Tracking**:
  - Visual level map with locked/unlocked/current/completed states
  - XP accumulation (10 XP per correct answer)
  - Star ratings per tier
  - Relationship-specific progress tracking

**User Flow**:
1. User fills out "My Specs" with personal answers
2. Partner attempts quiz about user's specs
3. System generates questions from user's answers
4. Partner answers quiz questions
5. System awards XP and stars
6. Unlocks next tier when current tier completed with 3 stars

**Categories**:
- Dreams & Aspirations
- Stress Triggers
- Comfort & Preferences
- Childhood Memories
- Values & Beliefs
- Affection Styles
- Conflict Resolution
- Future Plans
- Hobbies & Interests
- Fears & Concerns

---

### 5. Relational Economy & Marketplace Module

**Purpose**: Personalized currency system for relationship transactions

**Features**:
- **Economy Configuration**:
  - Custom currency name and symbol (e.g., "Love Tokens 🪙", "Hearts ❤️")
  - Per-user currency settings
  - Preset options or custom creation
- **Market Items**:
  - **SPEND Items** (Offers): Things user offers to give (e.g., "Breakfast in Bed", "1 Hour Massage")
  - **EARN Items** (Requests/Bounties): Tasks user wants done (e.g., "Wash Dishes", "Plan Date Night")
  - Item properties: title, description, cost, icon/emoji, category
  - Availability settings (visible to specific relationships or all)
  - Optional descriptions (collapsible)
- **Transaction Flow**:
  - **SPEND Flow**: Purchase → Redeem
  - **EARN Flow**: Accept → Submit for Review → Approve → Currency Paid
  - Verification system for completed tasks
  - Transaction history tracking
- **My Vault**:
  - **My Offers**: User's SPEND items
  - **My Requests**: User's EARN items
  - **Trades**: Active transactions (purchased, accepted, pending approval, etc.)
- **Balance Management**:
  - Per-relationship currency balances
  - Transaction-based balance updates
  - Idempotency for concurrent transactions

**User Flow**:
1. User configures their currency (name + symbol)
2. User creates market items (offers or requests)
3. Partner views user's market and purchases/accepts items
4. For EARN items: Partner completes task → Submits for verification → User approves → Currency transferred
5. For SPEND items: Partner purchases → Redeems when ready

**Transaction States**:
- `purchased` - Item bought, in vault, waiting to be used
- `redeemed` - SPEND item used/consumed
- `accepted` - EARN task taken, in progress
- `pending_approval` - Task marked done, waiting for issuer confirmation
- `approved` - Task confirmed, currency paid
- `canceled` - Transaction abandoned

---

### 6. Therapist Mode

**Purpose**: AI-powered conflict resolution and relationship counseling

**Features**:
- **Subject Selection**: Choose partner or loved one to discuss
- **Chat Interface**: Conversational AI therapist
- **Session Types**:
  - Individual counseling
  - Mediation mode (partner perspective simulation)
  - Appreciation exercises
  - Breathing/calming exercises
- **AI Capabilities**:
  - Context-aware responses
  - Partner perspective simulation
  - Conflict analysis
  - Relationship advice
  - Guided exercises

**User Flow**:
1. User selects subject (partner/loved one)
2. Describes situation or conflict
3. AI provides guidance and asks questions
4. User can request partner perspective
5. System guides through resolution process

---

### 7. Activities Mode

**Purpose**: Suggested activities and date ideas for couples

**Features**:
- Activity suggestions based on relationship context
- Activity types: Romantic, Fun, Deep, Active
- XP rewards for completed activities
- Memory tracking
- Activity history

**User Flow**:
1. User views suggested activities
2. Selects activity to do with partner
3. Completes activity
4. Records memory/notes
5. Earns XP

---

### 8. Personal Profile Module

**Purpose**: User profile management and settings

**Features**:
- **Tabbed Interface**:
  - **Basic Info**: Profile picture, name, ID, gender, description, interests, attachment style, analytics
  - **Personality**: MBTI sliders, personality type display
  - **Communication**: Voice print status and re-recording
  - **Insider Settings**: Love currency configuration, Love Map settings (TBD)
- **Inline Editing**: Edit individual attributes with save/cancel
- **Profile Picture Management**: Avatar picker with MBTI-based avatars
- **Voice Print Management**: View status, re-record voice print
- **Analytics**: Overall affection score, communication score, weekly trends

**User Flow**:
1. User taps their profile icon
2. Personal profile panel slides in from right
3. User navigates tabs
4. Clicks edit button on specific attribute
5. Makes changes and saves

---

### 9. Relationship Management Module

**Purpose**: Managing relationships with loved ones

**Features**:
- **Add Relationships**:
  - Email-based lookup
  - If user exists: Create relationship directly
  - If user doesn't exist: Generate invite link
  - Native share interface (mobile) or copyable link (web)
- **Relationship Status**:
  - Pending (invite sent, not accepted)
  - Active (both parties accepted)
- **Relationship Details**:
  - Relationship type (Partner, Family, Friend, etc.)
  - Member status tracking
  - Consent management
- **Invite System**:
  - Email invitations via SendGrid (optional)
  - Invite tokens with expiration
  - Pre-filled signup information
  - Relationship type pre-configured

**User Flow**:
1. User enters email of loved one
2. System checks if user exists
3. If exists: Creates relationship
4. If not: Generates invite link
5. User shares invite (native share or copy link)
6. Recipient signs up with invite token
7. Relationship automatically created

---

### 10. Interaction Module (Pokes & Reactions)

**Purpose**: Lightweight communication and connection

**Features**:
- **Emoji Reactions**: Send emojis to loved ones
- **Real-time Delivery**: WebSocket-based instant delivery
- **Visual Indicators**: 
  - Small emoji icon on sender's avatar (recipient's view)
  - Animation effects (jumping animation for 15 seconds)
  - Time-based display (only shows if sent <30 seconds ago)
- **Notification System**: Web/phone notifications for received reactions

**User Flow**:
1. User long-presses on loved one's avatar
2. Emoji picker appears
3. User selects emoji
4. System sends via WebSocket
5. Recipient receives notification
6. Emoji appears on sender's avatar in recipient's dashboard
7. Animation plays for 15 seconds

---

## User Workflows

### New User Onboarding Flow

```
1. Sign Up
   ↓
2. Complete Onboarding Steps:
   - Identity (name, gender, profile picture)
   - Personality (MBTI sliders)
   - Voice Print (biometric enrollment)
   - Add Loved Ones (email lookup + invites)
   ↓
3. Enter Dashboard
   ↓
4. Explore Rooms and Features
```

### Adding a Relationship Flow

```
1. User enters email
   ↓
2. System checks if user exists
   ↓
3a. User EXISTS:
    - Create relationship immediately
    - Add to Active Units tray
   ↓
3b. User DOESN'T EXIST:
    - Generate invite token
    - Create pending relationship
    - Show share interface
    ↓
4. Recipient receives invite
   ↓
5. Recipient signs up with token
   ↓
6. Relationship automatically created
   ↓
7. Both users see relationship in Active Units
```

### Love Maps Gameplay Flow

```
1. User A fills out "My Specs"
   - Answers questions about themselves
   - Categorizes by difficulty tier
   ↓
2. User B views User A's Love Map
   - Sees available tiers
   - Unlocked tiers (≥3 specs)
   - Locked tiers (<3 specs)
   ↓
3. User B starts quiz for unlocked tier
   ↓
4. System generates questions:
   - Selects random specs from tier
   - Creates multiple choice questions
   - Generates AI distractors
   ↓
5. User B answers questions
   ↓
6. System calculates score:
   - Awards XP (10 per correct)
   - Calculates star rating
   ↓
7. If 3 stars: Unlocks next tier
   ↓
8. Progress tracked per relationship
```

### Marketplace Transaction Flow (EARN)

```
1. User A creates EARN item:
   - "Wash Dishes" for 150 tokens
   ↓
2. User B views User A's market
   ↓
3. User B accepts task
   - Transaction created (status: ACCEPTED)
   ↓
4. User B completes task
   ↓
5. User B submits for review
   - Status: PENDING_APPROVAL
   ↓
6. User A receives verification request
   ↓
7. User A confirms completion
   - Status: APPROVED
   - Currency transferred to User B
   - User B's balance increases
```

### Marketplace Transaction Flow (SPEND)

```
1. User A creates SPEND item:
   - "Breakfast in Bed" for 500 tokens
   ↓
2. User B views User A's market
   ↓
3. User B purchases item
   - Transaction created (status: PURCHASED)
   - Currency deducted from User B's balance
   ↓
4. Item appears in User B's vault
   ↓
5. User B redeems item when ready
   - Status: REDEEMED
   - User A provides service
```

### Dialogue Deck Session Flow

```
1. User enters Dialogue Deck
   ↓
2. System checks voice print
   - If missing: Prompt setup
   - If exists: Proceed
   ↓
3. User starts conversation
   ↓
4. System captures audio:
   - Continuous microphone input
   - Real-time processing
   ↓
5. Analysis happens:
   - Speaker identification
   - Transcription (ASR)
   - Sentiment analysis
   - Four Horsemen detection
   ↓
6. Visual feedback:
   - Transcript with speaker labels
   - Sentiment indicators
   - Alert notifications
   ↓
7. Coaching nudges appear
   ↓
8. User ends session
```

---

## User Experiences

### Dashboard Experience

The dashboard serves as the central hub, designed as a floor plan with "rooms" representing different features:

- **Visual Design**: Clean, modern interface with slate color scheme
- **Active Units Tray**: Top section showing all loved ones as interactive avatars
- **Room Grid**: 3x2 grid of rooms, each with distinct icon and purpose
- **Real-time Updates**: WebSocket-powered live updates for emoji reactions
- **Smooth Transitions**: Animated transitions between modes
- **Responsive Layout**: Adapts to different screen sizes

### Love Maps Experience

- **Gamification**: Level-based progression with visual map
- **Knowledge Building**: Encourages partners to learn about each other
- **Achievement System**: Stars and XP create sense of accomplishment
- **Discovery**: "Discover" tab shows unanswered questions to encourage completion
- **Personalization**: Each relationship has independent progress tracking

### Marketplace Experience

- **Personalization**: Each user has their own currency and market
- **Flexibility**: Users control what they offer and request
- **Trust System**: Verification process ensures task completion
- **Transparency**: Clear transaction history and status tracking
- **Engagement**: Makes relationship tasks fun and rewarding

### Dialogue Deck Experience

- **Real-time Feedback**: Immediate insights during conversations
- **Non-intrusive**: Visual indicators don't interrupt flow
- **Educational**: Helps users recognize communication patterns
- **Privacy**: Voice data used only for speaker identification
- **Accessibility**: Requires voice print setup for security

---

## Technical Architecture

### Backend Architecture

**Tech Stack**:
- Python 3.11
- FastAPI (REST + WebSockets)
- SQLAlchemy 2.0 (async ORM)
- PostgreSQL (database)
- Redis (job queue + rate limiting)
- Alembic (migrations)
- JWT (authentication)
- SendGrid (email, optional)

**Architecture Pattern**: Clean Architecture with strict layering

```
app/
  api/          # FastAPI routes (HTTP/WS endpoints)
  domain/       # Business logic (models, services, policies)
  infra/        # Infrastructure (DB, Redis, security, WS manager)
```

**Domain Modules**:
- `admin/` - User management, relationships, consent
- `coach/` - Session management, analysis engines
- `interaction/` - Pokes, emojis, WebSocket handling
- `love_map/` - Love Maps game logic, quiz generation
- `market/` - Economy, transactions, marketplace
- `onboarding/` - Onboarding flow logic
- `voice/` - Voice enrollment and verification

### Frontend Architecture

**Tech Stack**:
- React + TypeScript
- Vite (build tool)
- Capacitor (mobile app framework)
- WebSocket client for real-time features
- Gemini API integration for AI features

**Component Structure**:
- `components/` - React components for each mode
- `services/` - API service layer, audio utilities, Gemini integration
- `types.ts` - TypeScript type definitions

**Key Components**:
- `App.tsx` - Main application with mode routing
- `AuthScreen.tsx` - Authentication UI
- `Onboarding.tsx` - Multi-step onboarding
- `LiveCoachMode.tsx` - Dialogue Deck
- `LoveMapsMode.tsx` - Love Maps game
- `RewardsMode.tsx` - Marketplace
- `TherapistMode.tsx` - AI therapist
- `PersonalProfilePanel.tsx` - Profile management
- `BiometricSync.tsx` - Voice print enrollment
- `AvatarPicker.tsx` - Avatar selection
- `MBTISliders.tsx` - Personality assessment

### Data Flow

**Authentication Flow**:
```
User → AuthScreen → apiService.login/signup → Backend JWT → Store token → Load user
```

**Real-time Communication**:
```
User Action → WebSocket → Backend → Redis Bus → WebSocket → Other Users
```

**Market Transactions**:
```
User Action → API Request → Domain Service → Database → Transaction Created → Balance Updated → WebSocket Notification
```

**Love Maps Quiz**:
```
User Request → API → Fetch Specs → Generate Questions (AI) → Return Quiz → User Answers → Calculate Score → Update Progress
```

---

## Key Features Summary

### Core Features

1. **Multi-user Relationship Platform**: Support for multiple relationships (partners, family, friends)
2. **Real-time Communication Coaching**: Live analysis during conversations
3. **Gamified Relationship Building**: Love Maps trivia system
4. **Relational Economy**: Personalized currency and marketplace
5. **AI-Powered Insights**: Therapist mode, sentiment analysis, pattern detection
6. **Voice Biometrics**: Speaker identification for conversation analysis
7. **Invite System**: Email-based relationship creation
8. **Profile Management**: Comprehensive user profiles with MBTI, interests, preferences

### Technical Features

1. **WebSocket Real-time Updates**: Instant emoji delivery, notifications
2. **Clean Architecture**: Maintainable, testable backend structure
3. **Mobile + Web Support**: Capacitor for cross-platform deployment
4. **Voice Processing**: Real-time audio analysis and transcription
5. **AI Integration**: Gemini API for quiz generation, coaching, therapy
6. **Transaction System**: Idempotent, concurrent-safe marketplace transactions
7. **Rate Limiting**: Prevents abuse of interaction features
8. **Email Integration**: Optional SendGrid for relationship invitations

### User Experience Features

1. **Intuitive Navigation**: Floor plan metaphor with rooms
2. **Visual Feedback**: Animations, indicators, real-time updates
3. **Personalization**: Custom currencies, avatars, profiles
4. **Gamification**: XP, stars, levels, achievements
5. **Accessibility**: Voice print setup prompts, clear UI
6. **Privacy**: Voice data used only for identification
7. **Flexibility**: Edit profiles, manage relationships, customize settings

---

## Future Enhancements (Planned)

- Vector embeddings for semantic matching in Love Maps
- Stale data notifications (if answers haven't been updated)
- Artifacts system (completed specs generate room decorations)
- Integration between Global XP and Economy Currency systems
- Enhanced analytics and insights dashboard
- Mobile app deployment (iOS/Android via Capacitor)
- Push notifications for mobile
- Advanced voice print quality testing
- Multi-language support
- Relationship health scoring

---

## Conclusion

Project Inside is a comprehensive platform that combines cutting-edge AI technology, gamification, and relationship psychology to create an engaging tool for improving relationships. By providing real-time coaching, gamified learning, and a relational economy, it transforms relationship improvement from a chore into an enjoyable, rewarding experience.

The platform's modular architecture allows for continuous enhancement while maintaining code quality and user experience. Each module serves a specific purpose in the relationship improvement journey, from initial onboarding through ongoing communication coaching and relationship building activities.
