# Visa Interviewer — Voice Frontend

A small Vite + React + TypeScript client for the voice visa interview. It picks a
visa type, joins a LiveKit room, streams live transcripts (officer + applicant),
lets you mute/unmute the mic, and renders the scored report when the interview
ends.

## Prerequisites

1. The FastAPI backend running with voice configured (LiveKit, Deepgram,
   ElevenLabs keys set). See the repo root `README.md`.
2. The LiveKit voice agent worker running:

   ```bash
   uv run python -m app.voice.agent dev
   ```

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # optional; defaults work with the Vite dev proxy
npm run dev
```

Open http://localhost:5173. The dev server proxies `/config`, `/voice`, and
`/interview` to `http://localhost:8000` (override with `VITE_API_PROXY`).

## How it works

- `GET /config` lists the available interviews and whether voice is enabled.
- `POST /voice/token` returns a LiveKit token (with the chosen country/visa in
  the participant metadata).
- The browser connects to LiveKit; the agent worker speaks the officer turns and
  transcribes your speech via Deepgram.
- The agent publishes the `session_id` over a data message; the client polls
  `GET /interview/{session_id}/report` and shows the report on completion.
