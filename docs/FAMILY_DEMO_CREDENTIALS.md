# Demo Family: Credentials & Backstories

**For development and QA only. Do not use in production.**

---

## Logins

All three accounts use the same password for convenience:

| Role    | Email                         | Password       | Display name    |
|---------|--------------------------------|----------------|-----------------|
| Partner | `marcus.rivera@demo.inside.app` | `DemoFamily2025!` | Marcus Rivera   |
| Partner | `priya.rivera@demo.inside.app`  | `DemoFamily2025!` | Priya Rivera    |
| Child   | `sam.rivera@demo.inside.app`   | `DemoFamily2025!` | Sam Rivera      |

**Relationship:** Priya and Marcus are partners; Sam is their child (they are Sam's parents).

---

## Personal descriptions & hobbies (in DB)

### Marcus Rivera (Partner / Dad)
- **Personal description:** I’m a software engineer and dad. I need some quiet time to recharge—running or a good book does it. I’m not great at talking about feelings but I try to show up for my family by doing stuff: fixing things, making coffee, being there.
- **Hobbies:** Running, Reading sci-fi, Bike rides, Fixing things around the house, Hiking

### Priya Rivera (Partner / Mom)
- **Personal description:** I do UX design part-time and the rest of the time I’m mostly thinking about my people. I love when we’re all in the same room and actually talking. Also trying to grow herbs on our balcony—mixed results so far.
- **Hobbies:** Gardening, Baking, Podcasts, Family movie nights, Planning trips

### Sam Rivera (Child, 10)
- **Personal description:** I’m in 5th grade. I like drawing and building stuff and our dog Bean is the best. I get tired after school so I need quiet sometimes. I like it when we do things together and nobody’s on their phone.
- **Hobbies:** Drawing, Minecraft, LEGO, Reading fantasy, Playing with Bean

---

## Backstories (short)

### Marcus Rivera (Partner / Dad)
- 38, software engineer (remote 2 days/week). INTJ.
- Interacts: calm, dry humor, acts of service; stressed by last‑minute changes.
- Recent: big release at work; agreed to coach kid’s robotics club.

### Priya Rivera (Partner / Mom)
- 36, part‑time UX designer, school library volunteer. ENFJ.
- Interacts: warm, words of affirmation, remembers details; stressed by conflict.
- Recent: herb garden on balcony; organized Marcus’s surprise birthday.

### Sam Rivera (Child, 10)
- 5th grade. INFP.
- Interacts: curious, needs quiet after school; opens up when doing things side‑by‑side.
- Recent: joined robotics club; excited about a sleepover at a friend’s.

---

## Seeding & cleanup

- **Seed (local):** From repo root: `cd backend && python scripts/seed_demo_family.py`  
  (Run after DB migrations and `python scripts/seed_love_map_prompts.py`.)
- **Seed (remote server):** To inject the demo family into the **remote** DB (e.g. DigitalOcean), set `DATABASE_URL` to the remote Postgres URL, then from `backend/` run:
  ```bash
  DATABASE_URL="postgresql://user:pass@host:25060/defaultdb?sslmode=require" ./scripts/seed_remote_demo_family.sh
  ```
  That script runs migrations, Love Map prompts, and demo family in order. See **docs/DEPLOY_DIGITALOCEAN.md** (Inject demo family to remote server).
- **Cleanup:** `cd backend && python scripts/cleanup_demo_family.py`  
  For remote: use the same `DATABASE_URL` and run `python scripts/cleanup_demo_family.py`.

Full user story and data details: `docs/FAMILY_DEMO_USER_STORY.md`.
