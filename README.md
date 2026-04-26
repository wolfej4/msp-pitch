# MSP Client Pitch

A self-hosted web app to help you run discovery conversations with MSP prospects, build a proposal in real time with AI suggestions, and export/email the result as a PDF.

Designed to run as a single container on Unraid / Portainer.

## Features

- **AI-assisted discovery** — chat with an LLM that knows your service catalog and the active prospect's context. The model recommends services by name; click any bolded service in chat to add it to the proposal.
- **Editable service catalog** — comes pre-seeded with ~20 common MSP offerings (Foundation, Cybersecurity, Cloud, Backup, Network, VoIP, Strategic, Compliance, plus a hospitality add-on). Edit pricing/units to fit your market.
- **Live proposal builder** — recurring (monthly/annual) and one-time line items with computed totals.
- **PDF export** — clean, branded proposal generated with WeasyPrint.
- **SMTP send** — email the PDF directly from the app.
- **LLM choice** — Anthropic API or local Ollama. Supports streaming responses.
- **No external state** — SQLite file in a bind-mounted volume.

## Quick start (Portainer Stack)

1. Create a directory on your Unraid box for the bind mount:
   ```bash
   mkdir -p /mnt/user/appdata/msp-pitch/data
   ```
2. In Portainer → **Stacks → Add stack**, paste in `docker-compose.yml`, override the `volumes` line to point at your appdata path:
   ```yaml
   volumes:
     - /mnt/user/appdata/msp-pitch/data:/app/data
   ```
3. Add the env vars (see `.env.example`) in Portainer's "Environment variables" panel. At minimum:
   - `LLM_PROVIDER` = `ollama` or `anthropic`
   - If `ollama`: `OLLAMA_BASE_URL` (default uses `host.docker.internal:11434`) and `OLLAMA_MODEL`
   - If `anthropic`: `ANTHROPIC_API_KEY`
4. **Build & deploy.** Browse to `http://<your-host>:8080`.

To put it behind your existing NPM at `pitch.wolfe.house`, just point a proxy host at the container on port `8000` (internally) or `8080` (via host) — same pattern you use for your other Wolfden services.

## Local run (for testing)

```bash
cp .env.example .env
# edit .env
docker compose up --build
```

## LLM options

### Anthropic
Set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=...`. Default model is `claude-sonnet-4-5`.

### Ollama (self-hosted)
Set `LLM_PROVIDER=ollama`. Default URL is `http://host.docker.internal:11434`, which lets the container reach Ollama running on the Unraid host (the `extra_hosts` entry in compose enables this on Linux).

If your Ollama runs on a different machine, point `OLLAMA_BASE_URL` at it (e.g. `http://192.168.1.50:11434`).

For best results with reasoning + service recommendations, use `llama3.1:8b` or larger, `qwen2.5:14b`, or any model you've validated. Smaller models tend to ramble.

## Service catalog

The catalog seeds on first launch from `app/services_seed.py`. Once seeded, the file is **not** consulted again — manage everything from the **Service Catalog** tab in the UI.

If you want to reset to defaults: stop the container, delete `data/msp.db`, restart.

## Auth / putting it on the internet

The app has no built-in auth — assumes you're either keeping it on LAN or fronting it with your existing Pocket ID + NPM setup. To enforce SSO:
- In NPM, add an Access List or use the OIDC integration you already have wired up for Wallos / OwnTracks.
- Don't expose port 8080 directly to the internet without auth.

## Backup

The whole thing is one SQLite file at `data/msp.db`. Back up the `data/` directory.

## Project layout

```
msp-pitch/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
└── app/
    ├── main.py            # FastAPI routes
    ├── config.py          # env-driven settings
    ├── database.py        # SQLAlchemy setup
    ├── models.py          # ORM models
    ├── schemas.py         # Pydantic schemas
    ├── llm.py             # Anthropic + Ollama streaming clients
    ├── pdf_generator.py   # WeasyPrint -> PDF
    ├── email_sender.py    # aiosmtplib
    ├── services_seed.py   # default catalog
    ├── templates/
    │   └── proposal.html  # PDF template
    └── static/
        ├── index.html
        ├── app.js
        └── styles.css
```
