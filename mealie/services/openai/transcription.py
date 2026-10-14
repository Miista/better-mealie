import functools
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypedDict

from mealie.core import exceptions
from mealie.core.config import get_app_settings
from mealie.core.root_logger import get_logger

from .openai import OpenAIService

SUBTITLE_LANGS = ["en", "fr", "es", "de", "it"]

logger = get_logger()


class TranscribedAudio(TypedDict):
    audio: Path | None
    subtitle: Path | None
    title: str
    description: str
    thumbnail_url: str | None
    transcription: str


@functools.cache
def get_yt_dlp_extractors() -> list:
    """Build and cache the yt-dlp extractor list once per process lifetime."""
    import yt_dlp
    from yt_dlp.extractor.generic import GenericIE

    return [ie for ie in yt_dlp.extractor.gen_extractors() if ie.working() and not isinstance(ie, GenericIE)]


def is_video_url(url: str) -> bool:
    """Whether yt-dlp recognizes the URL as something it can download."""

    if not url:
        return False

    return any(ie.suitable(url) for ie in get_yt_dlp_extractors())


def parse_subtitle_content(subtitle_content: str) -> str:
    # TODO: is there a better way to parse subtitles that's more efficient?

    lines = []
    for line in subtitle_content.split("\n"):
        if line.strip() and not line.startswith("WEBVTT") and "-->" not in line and not line.isdigit():
            lines.append(line.strip())

    raw_content = " ".join(lines)
    content = re.sub(r"<[^>]+>", "", raw_content)
    return content


def download_video(url: str, temp_path: Path) -> TranscribedAudio:
    """Downloads audio and subtitles from a video URL."""

    import yt_dlp

    output_template = temp_path / "mealie"  # No extension here

    # Capture yt-dlp's own error/warning messages so we can surface a
    # specific reason (login required, removed, region/age gated, extractor
    # breakage) instead of the generic "video may be unavailable" message.
    # NOTE: extract_info runs with ignoreerrors=True below and returns None
    # on failure, discarding the real cause — this logger buffer preserves it.
    ydl_messages: list[str] = []

    class _MessageLogger:
        def debug(self, msg):
            pass

        def info(self, msg):
            pass

        def warning(self, msg):
            ydl_messages.append(str(msg))

        def error(self, msg):
            ydl_messages.append(str(msg))

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_template) + ".%(ext)s",
        "quiet": True,
        "logger": _MessageLogger(),
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": SUBTITLE_LANGS,
        "skip_download": False,
        "ignoreerrors": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "32",
            }
        ],
        "postprocessor_args": ["-ac", "1"],
    }

    settings = get_app_settings()
    if settings.YTDLP_COOKIEFILE:
        ydl_opts["cookiefile"] = settings.YTDLP_COOKIEFILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            if info is None:
                yt_dlp_reason = " | ".join(ydl_messages).strip()
                if yt_dlp_reason:
                    logger.error(f"yt-dlp could not extract video from {url} — reason: {yt_dlp_reason}")
                else:
                    logger.error(
                        f"yt-dlp could not extract video from {url} — no reason reported "
                        "(video may be private, removed, region/age restricted, or require login)"
                    )
                raise exceptions.VideoDownloadError(
                    "Failed to extract video information. The video may be private, removed, "
                    "region/age restricted, require login, or the URL is invalid."
                    + (f" (yt-dlp: {yt_dlp_reason})" if yt_dlp_reason else "")
                )

            sub_path = None
            for lang in SUBTITLE_LANGS:
                potential_path = output_template.with_suffix(f".{lang}.vtt")
                if potential_path.exists():
                    sub_path = potential_path
                    break

            return {
                "audio": output_template.with_suffix(".mp3"),
                "subtitle": sub_path,
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "thumbnail_url": info.get("thumbnail") or None,
                "transcription": "",
            }
    except exceptions.VideoDownloadError:
        raise
    except Exception as e:
        raise exceptions.VideoDownloadError(f"Failed to download video: {e}") from e


def og_fallback(html: str | None) -> TranscribedAudio | None:
    """
    Builds video data from the page's Open Graph tags, for when yt-dlp can't download the
    video (e.g. Instagram requires login). Returns None if the page has no og:description.
    """

    if not html:
        return None

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    def og(name: str) -> str:
        tag = soup.find("meta", property=name)
        return str(tag.get("content") or "").strip() if tag else ""

    description = og("og:description")
    if not description:
        return None

    return {
        "audio": None,
        "subtitle": None,
        "title": og("og:title"),
        "description": description,
        "thumbnail_url": og("og:image") or None,
        "transcription": "",
    }


def download_video_or_og(url: str, temp_path: Path, html: str | None) -> TranscribedAudio:
    """Downloads the video, falling back to the page's Open Graph data if yt-dlp fails."""

    try:
        return download_video(url, temp_path)
    except exceptions.VideoDownloadError:
        if (fallback := og_fallback(html)) is None:
            raise
        logger.info(f"yt-dlp failed, falling back to OG description for {url}")
        return fallback


def read_subtitles(video_data: TranscribedAudio) -> str:
    """Reads the downloaded subtitle file, if there is one. Returns an empty string on failure."""

    subtitle_path = video_data["subtitle"]
    if not subtitle_path:
        return ""

    try:
        with open(subtitle_path, encoding="utf-8") as f:
            subtitle_content = f.read()

        logger.info("Using subtitles from video instead of transcription")
        return parse_subtitle_content(subtitle_content)
    except Exception:
        logger.exception("Failed to read subtitles, falling back to transcription")
        return ""


async def resolve_transcription(
    video_data: TranscribedAudio,
    openai_service: OpenAIService,
    before_transcribe: Callable[[], Awaitable[None]] | None = None,
) -> str:
    """
    Resolves a video's transcript, preferring one that's already known, then its subtitles,
    and falling back to transcribing the audio with AI. `before_transcribe` is awaited only
    if that fallback is needed.
    """

    if video_data["transcription"]:
        return video_data["transcription"]

    if subtitles := read_subtitles(video_data):
        return subtitles

    # nothing to transcribe (OG fallback); the description is all we have
    if video_data["audio"] is None:
        return ""

    if before_transcribe:
        await before_transcribe()

    try:
        transcript = await openai_service.transcribe_audio(video_data["audio"])
    except exceptions.RateLimitError:
        raise
    except Exception as e:
        raise exceptions.OpenAIServiceError(f"Failed to transcribe audio: {e}") from e

    if not transcript:
        raise exceptions.OpenAIServiceError("No transcription returned from OpenAI")

    return transcript
