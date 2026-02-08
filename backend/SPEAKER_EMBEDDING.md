# Speaker embedding (ECAPA-TDNN via SpeechBrain)

Speaker identification in STT uses **192-dimensional embeddings** from [SpeechBrain](https://speechbrain.readthedocs.io/)'s **ECAPA-TDNN** model (`speechbrain/spkrec-ecapa-voxceleb`).

## Installation

Speaker embedding is included in the main backend dependencies. No extra install or LLVM is required.

```bash
cd backend
poetry install
# or: pip install -r requirements.txt
```

This installs `speechbrain`, which pulls in PyTorch and torchaudio as needed.

## Usage

- **Enrollment:** Voice samples (WAV) are resampled to **16 kHz** mono, then encoded with ECAPA-TDNN; embeddings are stored in the profile. Resampling ensures enrollment and STT segments use the same input space (ECAPA expects 16 kHz).
- **STT:** Each final segment (16 kHz PCM) is encoded with ECAPA-TDNN and matched to enrolled users via cosine similarity.

If `speechbrain` is not installed in the Python env that runs the server, the app still runs but speaker IDs will show 0% and the startup log will warn: `Speaker encoder: ... (Install: pip install speechbrain)`.

## Reference

- [SpeechBrain docs](https://speechbrain.readthedocs.io/en/latest/)
- [Speaker recognition (EncoderClassifier, ECAPA-TDNN)](https://speechbrain.readthedocs.io/en/latest/API/speechbrain.inference.speaker.html)
- [spkrec-ecapa-voxceleb on Hugging Face](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb)
