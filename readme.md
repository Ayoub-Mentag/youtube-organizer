# YouTube Watch Later Organizer

Hundreds of videos piled up in Watch Later? This tool sorts them into playlists
(AI, Programming, Finance, ...) using a **local AI model**. Your video list never
leaves your machine, except for calls to the official YouTube API.

```
Takeout CSV --> fetch (YouTube API) --> classify (local Qwen via Ollama) --> push (private playlists)
```

1. **fetch**: reads your Watch Later export and looks up each video's title and channel.
2. **classify**: a local LLM assigns each video to one of your categories (`config.yaml`).
3. **push**: creates one **private** playlist per category and adds the videos.

Everything runs in Docker, except Ollama (so it can use your GPU).

## Requirements

- Docker (with Compose) and `make`
- [Ollama](https://ollama.com) app, with the model: `ollama pull qwen2.5:7b`
- A Google account and a free Google Cloud project (an API key and an OAuth client)
- About 8 GB of free RAM for the 7B model

## Setup (one time, about 15 minutes)

**1. Export your Watch Later list.** The YouTube API cannot read Watch Later, so use Google Takeout:
[takeout.google.com](https://takeout.google.com) > Deselect all > **YouTube and YouTube Music** >
only **playlists** > export. In the zip, take `Watch later-videos.csv`, rename it to
`watch-later-videos.csv`, and put it in a `data/` folder in this project.

**2. Create the Google credentials** in [Google Cloud Console](https://console.cloud.google.com):
- Create a project and enable **YouTube Data API v3**.
- **API key** (Credentials > Create credentials > API key). Restrict it to YouTube Data API v3.
  Used to read video titles.
- **OAuth client ID**, type **Desktop app**. Download the JSON as `data/client_secret.json`.
  Used to create playlists in your account.
- On the OAuth consent screen, add your own email as a **test user**.

**3. Add your API key:**
```
cp .env.example .env     # then edit .env and paste your key
```

**4. Start the Ollama app** and pull the model (see Requirements).

## Run

```
make up
```

That runs fetch, classify and push in order. The first push opens a Google login link in
your terminal. Approve it in your browser, and the script continues by itself.

| Command | What it does |
| --- | --- |
| `make up` | Everything. Safe to re-run: every step resumes where it stopped |
| `make fetch` / `make classify` | Run one step |
| `make push-preview` | Show which playlists would be created, change nothing |
| `make push` | Create the playlists and add the videos |
| `make reset` | Delete the fetched and classified data and start over |

## Project layout

```
src/           fetch.py, classify.py, push.py (one script per step)
config.yaml    model and categories
data/          your private files (git-ignored)
```

## Customize

Edit `config.yaml`: the model, the categories, and a short description of each one
(the descriptions matter, the model reads them). The model must pick one of your
categories for every video.

## Good to know

- **Playlists are private** and named `WL - <category>`. Existing playlists are never touched.
- **Watch Later is not emptied.** The API can add to playlists but cannot remove from Watch Later.
- **Quota:** YouTube allows about 200 playlist inserts per day, so a big list takes a couple
  of days. When the quota runs out the script stops cleanly. Run `make up` again the next day.
- Google shows an "unverified app" warning for your own test app. That is expected:
  click Advanced and continue.
- Docker on Mac cannot use the GPU, which is why Ollama runs natively. On Linux, Ollama may
  need to listen on all interfaces so the container can reach it (`OLLAMA_HOST=0.0.0.0`).

## Privacy and safety

- Classification runs locally. No video titles are sent to any AI service.
- Credentials (`.env`, `data/client_secret.json`, the saved login) are git-ignored.
  **Never commit them.** To revoke access: [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
- Each user brings their own Google credentials, so nothing is shared and there is no
  central server.