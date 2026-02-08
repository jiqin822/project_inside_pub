# Demo Family: User Story & Backstories

## Overview

The **Rivera family** is a fictional demo household used to test the app’s relationship features: Love Maps, Connection Market (rewards/quests), and family interactions. This document describes their user story, personalities, and how they use the product.

---

## The Family

**Relationship:** Priya and Marcus are partners; Sam is their child (they are Sam's parents).

### Marcus Rivera (Partner / Dad)
- **Role:** Father, 38. Software engineer, works from home two days a week.
- **Personality:** Calm, logical (INTJ). Prefers clear plans and alone time to recharge. Shows love through acts of service and quality time.
- **Hobbies:** Running, reading sci‑fi, fixing things around the house, weekend bike rides.
- **Ways he interacts:** Tends to listen more than talk; uses dry humor. Gets stressed by last‑minute changes. Comforts others by giving space or doing something practical (e.g. making tea, taking over a chore).
- **Recent events:** Just finished a big release at work. Agreed to coach the kid’s robotics club. Had a good “dads’ night out” with a neighbor last week.

### Priya Rivera (Partner / Mom)
- **Role:** Mother, 36. Part‑time UX designer, volunteer at the school library.
- **Personality:** Warm, organized, expressive (ENFJ). Values connection and making sure everyone feels heard.
- **Hobbies:** Gardening, baking, podcasts, family movie nights, planning small trips.
- **Ways she interacts:** Starts conversations, remembers details about people, uses words of affirmation and small gifts. Stressed by conflict or feeling unheard; comforts by talking things through and hugs.
- **Recent events:** Started a small herb garden on the balcony. Organized a surprise birthday for Marcus. Worried a bit about their 10‑year‑old’s screen time.

### Sam Rivera (Child, 10)
- **Role:** Only child, 5th grade.
- **Personality:** Curious, creative, a bit shy with new people (INFP). Sensitive to others’ moods, loves animals and stories.
- **Hobbies:** Drawing, Minecraft, reading fantasy, playing with the family dog (Bean), building LEGO.
- **Ways they interact:** Asks “why” a lot, needs quiet time after school. Opens up when doing something side‑by‑side (e.g. building LEGO with Dad, baking with Mom). Comforted by routines and gentle reassurance.
- **Recent events:** Joined the school robotics club. Lost a tooth last week. Excited about an upcoming sleepover at a friend’s house.

---

## User Story: A Week in the Rivera Household

**Goal:** Use the app to stay connected as a family—know each other better (Love Maps), trade small rewards and quests (Connection Market), and complete some activities together.

1. **Love Maps**
   - Each person has answered several prompts (Basics, Dreams, Stress, History, Intimacy).
   - Marcus and Priya have progress on each other’s maps (quiz level, XP, stars).
   - Sam has a few answers filled in; Mom and Dad have started “learning Sam’s map” (progress records).

2. **Connection Market**
   - **Mom’s economy:** “Heart Tokens” (🫀). She offers rewards (e.g. “Choose Friday movie”, “Extra 30 min screen time”) and quests (e.g. “Set the table without being asked”, “Read for 20 min”).
   - **Dad’s economy:** “High Fives” (✋). Rewards (e.g. “Bike ride with Dad”, “Help with a project”) and quests (e.g. “Practice robotics for 15 min”, “No complaining at dinner”).
   - **Sam’s economy:** “Stars” (⭐). Small rewards for parents (e.g. “Draw you a picture”) and quests (e.g. “Play a board game with me”).
   - Recent interactions: Mom “purchased” Sam’s “Draw you a picture” and marked it redeemed; Dad accepted Sam’s quest “Play a board game with me” and Sam marked it approved; Mom accepted Dad’s “Back massage” and it’s redeemed.

3. **Quests Completed Together**
   - **“Family game night”** – Initiated by Priya, completed by all three (planned activity / quest flow).
   - **“Robot build session”** – Marcus and Sam completed a robotics build; Sam submitted, Marcus approved (EARN quest in Dad’s economy).
   - **“Help set the table for a week”** – Sam accepted Mom’s quest and completed it; Priya approved (EARN quest in Mom’s economy).

4. **Outcome**
   - The family has richer Love Map data and visible progress.
   - Connection Market shows a mix of SPEND (rewards redeemed) and EARN (quests accepted → submitted → approved).
   - Quests and rewards feel tied to real routines (dinner, robotics, screen time, quality time).

---

## Data Summary for Seeding

| Area              | Marcus | Priya | Sam |
|-------------------|--------|--------|-----|
| Love Map answers  | ~12    | ~12    | ~8  |
| Map progress      | →Priya, →Sam | →Marcus, →Sam | →Marcus, →Priya |
| Economy           | High Fives ✋ | Heart Tokens 🫀 | Stars ⭐ |
| Market items       | SPEND + EARN | SPEND + EARN | SPEND + EARN |
| Transactions      | Purchases/redemptions + quests approved | Same | Same |

Relationship: one **FAMILY** relationship with all three as **ACCEPTED** members. Priya and Marcus are partners; Sam is their child (they are Sam's parents). Market items are visible to that relationship where applicable.

---

## How to Use This Family

- **Seeding:** Run `python backend/scripts/seed_demo_family.py` (after DB migrations and Love Map prompts seeded).
- **Cleanup:** Run `python backend/scripts/cleanup_demo_family.py` to remove the three users and all related data.
- **Credentials:** See `docs/FAMILY_DEMO_CREDENTIALS.md` for login emails and passwords.

This family is for development and QA only; do not use in production.
