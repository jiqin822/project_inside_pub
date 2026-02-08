# NeMo Sortformer Diarization Setup

Optional speaker diarization fallback when Google Cloud STT diarization is unavailable (e.g. `language_code=auto` or Chirp 3). Uses the streaming model [nvidia/diar_streaming_sortformer_4spk-v2.1](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1).

## 1. Python environment

Use the same Python as the rest of the backend (see `backend/.python-version` or project README). Recommended: a dedicated virtualenv.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 2. Install dependencies

Install main backend deps first, then NeMo:

```bash
pip install -r requirements.txt -r requirements-nemo.txt
```

If that fails (e.g. PyYAML or NeMo build errors), use the official NeMo install from the [Hugging Face model card](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1):

```bash
pip install Cython packaging
pip install -r requirements.txt
pip install git+https://github.com/NVIDIA/NeMo.git@main#egg=nemo_toolkit[asr]
```

NeMo is large and may pull in specific `torch`/`torchaudio` versions; if you hit conflicts, use a separate venv for a NeMo-enabled backend.

## 3. Environment variables

In `backend/.env` (or your environment):

| Variable | Required | Description |
|----------|----------|-------------|
| `STT_ENABLE_NEMO_DIARIZATION_FALLBACK` | No | Set to `true` to enable NeMo fallback (default: true). Set to `false` if NeMo is not installed to avoid startup warnings. |
| `HF_TOKEN` | No | Hugging Face token for gated/private models. The default model is public; only needed if you use a gated model. |
| `NEMO_DIAR_MODEL_PATH` | No | Path to a local `.nemo` checkpoint file. If set, the app loads this instead of downloading from Hugging Face. |
| `NEMO_CACHE_DIR` | No | Directory for NeMo/Hugging Face cache. Default: `$TMPDIR/nemo_cache` or `/tmp/nemo_cache`. |

Optional tuning (defaults are in `app/settings.py`; override via env):

- `STT_NEMO_DIARIZATION_WINDOW_S` – rolling window length in seconds (default: 12.0)
- `STT_NEMO_DIARIZATION_HOP_S` – hop between diarization runs in seconds (default: 2.0)
- `STT_NEMO_DIARIZATION_TIMEOUT_S` – inference timeout per window (default: 10.0)
- `STT_NEMO_DIARIZATION_MAX_SPEAKERS` – max speakers (default: 4)

**Minimal .env (enable fallback, use default model):**

```bash
# Enable NeMo diarization fallback (optional; default is true)
STT_ENABLE_NEMO_DIARIZATION_FALLBACK=true
```

**Disable NeMo (no install, no warning):**

```bash
STT_ENABLE_NEMO_DIARIZATION_FALLBACK=false
```

**Use a local .nemo file (no Hugging Face download):**

```bash
STT_ENABLE_NEMO_DIARIZATION_FALLBACK=true
NEMO_DIAR_MODEL_PATH=/path/to/diar_streaming_sortformer_4spk-v2.1.nemo
```

**Custom cache directory:**

```bash
NEMO_CACHE_DIR=/data/nemo_cache
```

## 4. Use the same env as the server

The server must run with a Python environment that has NeMo installed. Otherwise you’ll see “NeMo diarization fallback disabled” at startup even if `python scripts/check_nemo.py` passes in another env.

- **If you start the backend with `./start_dev.sh` and it uses Poetry** (message: “Starting backend server (Poetry env)...”), install NeMo in the Poetry env:
  ```bash
  cd backend
  poetry run pip install -r requirements-nemo.txt
  ```
- **If you start without Poetry** (e.g. plain `python3`), either:
  - Create and use a venv in `backend/`: `python3 -m venv .venv`, `source .venv/bin/activate`, `pip install -r requirements.txt -r requirements-nemo.txt`. Then `./start_dev.sh` will use that `.venv` when present.
  - Or run `./start_dev.sh` from a shell where you’ve already activated the same venv/conda env where you installed NeMo (and where `python scripts/check_nemo.py` passes).

## 5. Check NeMo deps

**From the command line (from `backend/`):**

```bash
python scripts/check_nemo.py
```

- Exit 0 and `nemo: OK  NeMo diarization available` if NeMo is usable.
- Exit 1 and `nemo: FAIL  <reason>` if not (e.g. `No module named 'nemo'`).

**One-liner:**

```bash
python -c "from app.domain.stt.nemo_sortformer_diarizer import nemo_diarization_available; ok, err = nemo_diarization_available(); print('ok' if ok else err); exit(0 if ok else 1)"
```

**From the running server:** `GET /ready` includes an optional `nemo` check. If NeMo is available you’ll see `"nemo": "ok"` in the response; otherwise the error message (e.g. `"NeMo not available: No module named 'nemo'"`). NeMo is optional and does not affect overall readiness (required checks are config, packages, database).

## 6. Verify

Start the backend and check logs:

- **NeMo available:**  
  `NeMo diarization fallback available (STT speaker labels when Google diarization unavailable)`
- **NeMo not installed / disabled:**  
  `NeMo diarization fallback disabled: ...` (warning) or no message if `STT_ENABLE_NEMO_DIARIZATION_FALLBACK=false`)

First run may download the model from Hugging Face (~hundreds of MB); ensure disk space and network access.

## 7. Optional: local model file

To avoid downloading at runtime, download the checkpoint once and point the app at it:

1. Install NeMo and run in Python:
   ```python
   from nemo.collections.asr.models import SortformerEncLabelModel
   model = SortformerEncLabelModel.from_pretrained("nvidia/diar_streaming_sortformer_4spk-v2.1")
   model.save_to("diar_streaming_sortformer_4spk-v2.1.nemo")
   ```
2. Set `NEMO_DIAR_MODEL_PATH` to the path of the saved `.nemo` file.
