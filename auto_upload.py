import os
import shutil
import requests
import subprocess

# ================== 設定 ==================
ANKI_CONNECT_URL = "http://localhost:8765"

BASE_DIR = "/home/takahashi-yutaro/API/anki_auto"
INBOX_FOLDER = os.path.join(BASE_DIR, "inbox")
DONE_FOLDER = os.path.join(BASE_DIR, "done")

ANKI_MEDIA = "/home/takahashi-yutaro/.local/share/Anki2/User 1/collection.media"

DECK_NAME = "englishsound"
MODEL_NAME = "EnglishSoundBasicClean"

WHISPER_BIN = "/home/takahashi-yutaro/whisper-venv/bin/whisper"
# ==========================================


def invoke(action, params=None):
    r = requests.post(
        ANKI_CONNECT_URL,
        json={
            "action": action,
            "version": 6,
            "params": params or {}
        },
        timeout=5
    )
    return r.json()


def is_anki_running():
    try:
        invoke("version")
        return True
    except Exception:
        return False


def note_exists(note_id):
    result = invoke("findNotes", {
        "query": f'ID:"{note_id}"'
    })
    return len(result.get("result", [])) > 0


# ===== Whisper 文字起こし =====
def transcribe_with_whisper(path):
    print("🧠 Transcribing with Whisper...")

    workdir = os.path.dirname(path)
    basename = os.path.splitext(os.path.basename(path))[0]
    txt_path = os.path.join(workdir, basename + ".txt")

    subprocess.run(
        [
            WHISPER_BIN,
            path,
            "--language", "English",
            "--output_format", "txt",
            "--output_dir", workdir,
            "--fp16", "False"
        ],
        check=True
    )

    if not os.path.exists(txt_path):
        raise RuntimeError("Whisper transcription failed")

    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def add_file_to_anki(path):
    filename = os.path.basename(path)

    if note_exists(filename):
        print(f"⏭ Already exists, move to done: {filename}")
        shutil.move(path, os.path.join(DONE_FOLDER, filename))
        return

    # 文字起こし
    transcript = transcribe_with_whisper(path)

    # media にコピー
    media_dest = os.path.join(ANKI_MEDIA, filename)
    if not os.path.exists(media_dest):
        shutil.copy(path, media_dest)













    note = {
     "deckName": DECK_NAME,
     "modelName": MODEL_NAME,
     "fields": {
        "ID": filename,
        "Front": f"""
<span class="desktop-only">
  [sound:{filename}]
</span>
<span class="android-only">
  <video controls>
    <source src="{filename}" type="video/mp4">
  </video>
</span>
""".strip(),
        "Back": transcript
    },
    "tags": ["auto", "sound", "whisper"]
}








    invoke("addNote", {"note": note})
    print(f"✅ Added with transcript: {filename}")

    # ===== 成功したら mp4 + txt を done に移動 =====
    dest_mp4 = os.path.join(DONE_FOLDER, filename)
    shutil.move(path, dest_mp4)

    txt_src = path.rsplit(".", 1)[0] + ".txt"
    if os.path.exists(txt_src):
        dest_txt = os.path.join(DONE_FOLDER, os.path.basename(txt_src))
        shutil.move(txt_src, dest_txt)


def main():
    if not is_anki_running():
        print("❌ Anki is not running")
        return

    os.makedirs(DONE_FOLDER, exist_ok=True)

    files = sorted(os.listdir(INBOX_FOLDER))
    if not files:
        print("ℹ️ Inbox is empty")
        return

    for filename in files:
        if not filename.lower().endswith((".mp3", ".wav", ".mp4")):
            continue

        path = os.path.join(INBOX_FOLDER, filename)
        if not os.path.isfile(path):
            continue

        try:
            add_file_to_anki(path)
        except Exception as e:
            # 失敗時は inbox に残す
            print(f"❌ Error processing {filename}: {e}")

    print("🎉 Finished")


if __name__ == "__main__":
    main()
