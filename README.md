# TaleSproutia

Automated English-language story video creation for a family audience.

## What this starter does

- Requests an original children's story from Groq.
- Creates English narration with Microsoft Edge TTS.
- Creates eight original illustrated storybook-style scene cards.
- Combines the cards and narration into an MP4 with FFmpeg.
- Uploads to YouTube only when all three YouTube OAuth secrets are configured.

**Visual note:** this first free version uses illustrated scene cards, not generated 3D animation. It is a low-cost starting point.

## GitHub repository secrets

In Settings → Secrets and variables → Actions → New repository secret, add:

| Name | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Groq API key (already added) |
| `YOUTUBE_CLIENT_ID` | Google OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | Google OAuth client secret |
| `YOUTUBE_REFRESH_TOKEN` | Refresh token with YouTube upload permission |

Never put API keys or OAuth tokens in source files.

## Daily schedule

The workflow runs at 00:00 UTC (09:00 Japan time) and can also be started from the Actions tab using Run workflow.

Uploads are currently set to private for safety. If YouTube OAuth secrets are missing, the workflow generates an MP4 and stores it as a GitHub Actions artifact for seven days, without uploading.

## Run locally

Requires Python 3.11+, FFmpeg, and the secrets above.

```bash
pip install -r requirements.txt
python story_video.py
```

## Free-tier limitations

Groq rate limits, GitHub Actions usage limits, and third-party text-to-speech availability can affect reliability. A scheduled workflow cannot guarantee a video every day.
