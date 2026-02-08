# Why activity cards might not use Gemini (LLM)

Activity cards are generated in two ways:

1. **LLM path (Gemini)** – personalized activities from the backend using Google Gemini.
2. **Seed fallback** – curated seed list when the LLM path is not used or fails.

**If activity cards never use the LLM:** The backend must have `google-genai` installed in the same Python environment that runs the server. If the import fails (e.g. server started without Poetry or `poetry install` not run), you will see seed fallback and no error in the request. **Fix:** From the backend directory run `poetry install` (or `pip install google-genai`), then restart the server with that environment (e.g. `./start_dev.sh` from backend/, which uses `poetry run` when Poetry is available). On startup the server logs either "google.genai available" or "google.genai could not be imported" with instructions.

If **GEMINI_API_KEY is already set** in `backend/.env` and you still see seed fallback, check **backend logs** when you load or refresh Discover. The backend now logs why Gemini was skipped or failed:

- `activity/recommendations: use_llm=false, using seed fallback` – client did not send `use_llm=true`.
- `activity/recommendations: GEMINI_API_KEY not set or empty, using seed fallback` – key not loaded at runtime (e.g. server started from wrong directory, or `.env` not in backend folder).
- `activity/recommendations: Gemini returned no activities, using seed fallback` – LLM was called but returned an empty or invalid list.
- `generate_activities_llm failed (seed fallback will be used): ...` – LLM call threw (e.g. invalid key, rate limit, network, or JSON parse error). Full exception is in the log.

## When Gemini is used

### Compass recommendations (`GET /v1/activity/recommendations`)

- The **client** already sends `use_llm=true` when loading or refreshing Discover (Game Room).
- The **backend** uses Gemini only when **both** are true:
  - `use_llm=true` (query param) ✓ (client sends this)
  - `GEMINI_API_KEY` is set and non-empty in the backend environment

If `GEMINI_API_KEY` is missing or empty, the backend skips the LLM and returns seed activities (debug source: `seed_fallback`).

### Coach suggestions (`GET /v1/coach/activities/suggestions`)

- No `use_llm` param; the backend uses Gemini whenever `GEMINI_API_KEY` is set.
- If the key is missing or empty, the backend returns seed activities.

## How to enable Gemini for activity cards

1. Get a Gemini API key: [Google AI Studio](https://aistudio.google.com/apikey).
2. In the **backend** project, set the key in `.env` (create from `backend/.env.example` if needed):

   ```bash
   GEMINI_API_KEY=your_key_here
   ```

3. Restart the backend server so it picks up the new env var.

After that, Compass recommendations (with `use_llm=true`) and Coach suggestions will use Gemini when the key is present. If the LLM call fails or returns no activities, the backend still falls back to the seed list.

## Quick check

- **Debug mode**: In the app, enable “Show debug” in your profile, then open an activity card and tap the Debug button. If you see “Seed fallback: curated list used when…” then the backend did not use the LLM for that card (missing key, or LLM returned empty).
- **Backend**: Ensure `backend/.env` contains a non-empty `GEMINI_API_KEY` and the server was restarted after adding it.
