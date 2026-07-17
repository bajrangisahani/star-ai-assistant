import asyncio
import os
import sys
import tempfile

import edge_tts
from playsound import playsound


VOICE = "en-US-GuyNeural"


async def make_audio(text, output_path):
    communicate = edge_tts.Communicate(
        text,
        voice=VOICE,
        rate="+5%",
        pitch="+0Hz",
    )
    await communicate.save(output_path)


def main():
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        return 0

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_path = temp_file.name
    temp_file.close()

    try:
        asyncio.run(make_audio(text, temp_path))
        playsound(temp_path)
        return 0
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
