import asyncio, json, os, random, subprocess, textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
W, H = 1280, 720
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
VOICE = os.getenv("TTS_VOICE", "en-US-AvaNeural")


def make_story():
    prompt = """Write an original, gentle English story for children ages 4-8.
The narration must be 700-850 words in simple spoken English, with a clear
beginning, middle and satisfying ending. Include kindness or curiosity.
Create exactly 8 short visual scene descriptions in story order.
No violence, frightening peril, copyrighted characters, franchises, songs,
or quoted books. Fill every requested field with complete content."""
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "narration": {"type": "string"},
            "scenes": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 8,
                "maxItems": 8
            }
        },
        "required": ["title", "description", "narration", "scenes"],
        "additionalProperties": False
    }
    payload = {
        "model": MODEL,
        "temperature": 0.6,
        "max_completion_tokens": 6000,
        "reasoning_effort": "low",
        "reasoning_format": "hidden",
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "childrens_story",
                "strict": True,
                "schema": schema
            }
        },
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"],
                 "Content-Type": "application/json"},
        json=payload, timeout=180
    )
    if not r.ok:
        raise RuntimeError(f"Groq API error {r.status_code}: {r.text[:2000]} (model={MODEL})")
    data = r.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            "Groq returned an empty story. "
            f"finish_reason={choice.get('finish_reason')}; model={MODEL}"
        )
    story = json.loads(content)
    word_count = len(story.get("narration", "").split())
    if word_count < 650:
        print(f"Story was short ({word_count} words); requesting one expansion.")
        payload["messages"] = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content},
            {"role": "user", "content": (
                "Expand and rewrite the narration in the story above. "
                "The narration MUST contain 700-850 words. "
                "Keep the same title, characters, plot and gentle ending. "
                "Do not summarize. Return the complete JSON object with exactly 8 scenes."
            )}
        ]
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"],
                     "Content-Type": "application/json"},
            json=payload, timeout=180
        )
        if not r.ok:
            raise RuntimeError(f"Groq expansion error {r.status_code}: {r.text[:2000]} (model={MODEL})")
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        expanded = message.get("content")
        if not isinstance(expanded, str) or not expanded.strip():
            raise RuntimeError(
                "Groq returned an empty expanded story. "
                f"finish_reason={choice.get('finish_reason')}; model={MODEL}"
            )
        story = json.loads(expanded)
        word_count = len(story.get("narration", "").split())
    if word_count < 600:
        raise ValueError(f"Story narration was too short after expansion ({word_count} words); expected at least 600.")
    if len(story["scenes"]) != 8:
        raise ValueError("Story must contain exactly 8 scenes.")
    return story

def get_font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size) if Path(path).exists() else ImageFont.load_default()


def make_card(title, description, number, folder):
    rng = random.Random(number * 173 + 29)
    colors = [((27,42,82),(102,119,168)), ((34,72,91),(118,166,151)),
              ((75,56,104),(184,131,155)), ((44,75,104),(139,172,181))]
    top, bottom = colors[(number-1) % len(colors)]
    img = Image.new("RGB", (W,H))
    px = img.load()
    for y in range(H):
        t = y/H
        c = tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(W): px[x,y] = c
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(65):
        x,y = rng.randrange(W),rng.randrange(H//2); rad=rng.randrange(2,5)
        d.ellipse((x-rad,y-rad,x+rad,y+rad),fill=(255,244,205,rng.randrange(90,220)))
    d.ellipse((920,95,1080,255),fill=(255,231,174,220))
    d.ellipse((-160,475,720,900),fill=(31,91,89,230))
    d.ellipse((430,500,1450,930),fill=(25,68,79,245))
    d.rounded_rectangle((70,65,1210,370),radius=34,fill=(9,18,38,125))
    d.text((110,95),f"TALESPROUTIA  •  CHAPTER {number}",font=get_font(25,True),fill=(255,222,157,255))
    y=155
    for line in textwrap.wrap(description,width=48)[:4]:
        d.text((110,y),line,font=get_font(30),fill=(255,255,255,255)); y+=48
    d.text((110,320),title[:70],font=get_font(22,True),fill=(255,232,190,255))
    path=folder/f"scene_{number:02d}.jpg"
    img.save(path,quality=90)
    return path


async def create_voice(text, path):
    await edge_tts.Communicate(text, VOICE, rate="-3%").save(str(path))


def audio_duration(path):
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)],
        capture_output=True,text=True,check=True)
    return float(p.stdout.strip())


def render(story, folder):
    audio=folder/"narration.mp3"
    asyncio.run(create_voice(story["narration"],audio))
    seconds=audio_duration(audio)/8
    cards=[make_card(story["title"],s,i+1,folder) for i,s in enumerate(story["scenes"])]
    listing=folder/"images.txt"
    with listing.open("w",encoding="utf-8") as f:
        for card in cards:
            f.write(f"file '{card.as_posix()}'\nduration {seconds:.3f}\n")
        f.write(f"file '{cards[-1].as_posix()}'\n")
    video=OUT/"talesproutia_latest.mp4"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listing),
        "-i",str(audio),"-vf","scale=1280:720,format=yuv420p","-c:v","libx264",
        "-preset","veryfast","-tune","stillimage","-c:a","aac","-b:a","192k",
        "-shortest","-movflags","+faststart",str(video)],check=True)
    return video


def upload(video, story):
    names=["YOUTUBE_CLIENT_ID","YOUTUBE_CLIENT_SECRET","YOUTUBE_REFRESH_TOKEN"]
    if not all(os.getenv(n) for n in names):
        print("YouTube OAuth not set; generated MP4 only.")
        return
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds=Credentials(token=None,refresh_token=os.environ[names[2]],
        token_uri="https://oauth2.googleapis.com/token",client_id=os.environ[names[0]],
        client_secret=os.environ[names[1]],scopes=["https://www.googleapis.com/auth/youtube.upload"])
    yt=build("youtube","v3",credentials=creds)
    privacy=os.getenv("YOUTUBE_PRIVACY_STATUS","private").lower()
    if privacy not in ("private","unlisted","public"): privacy="private"
    body={"snippet":{"title":story["title"][:100],
        "description":(story.get("description","")+"\\n\\nOriginal children's story by TaleSproutia.")[:5000],
        "categoryId":"1","defaultLanguage":"en"},
        "status":{"privacyStatus":privacy,"selfDeclaredMadeForKids":True}}
    result=yt.videos().insert(part="snippet,status",body=body,
        media_body=MediaFileUpload(str(video),chunksize=-1,resumable=True)).execute()
    print("YouTube video ID:",result.get("id"))


def main():
    if not os.getenv("GROQ_API_KEY"): raise RuntimeError("Missing GROQ_API_KEY secret.")
    story=make_story()
    folder=OUT/datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"story.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
    video=render(story,folder)
    (OUT/"latest_story_title.txt").write_text(story["title"],encoding="utf-8")
    upload(video,story)
    print("Video generated:",video)


if __name__=="__main__": main()
