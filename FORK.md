## better-mealie

Upstream Mealie with these changes layered on top (`Dockerfile` copies the patched files over the upstream image):

- **Translate every URL import** — set `BETTER_MEALIE_TRANSLATE_TO` (e.g. `Danish`) to run upstream's translation step after every URL import, including recipes read from a page's structured data that never reach the AI. Unset = off. On failure the untranslated recipe is kept.
- **Metric + clean names** — the translation prompt converts cups/oz/lb/tbsp/tsp/°F/inches to metric, and keeps the recipe name in its original language but strips view counts, emoji and promo text.
- **Real yt-dlp error reason** — video import failures report yt-dlp's own message instead of "video may be unavailable".
- **Open Graph fallback** — when yt-dlp can't download (e.g. Instagram login wall), import from the page's og:title/description/image and skip Whisper.

Releases are tagged `v<upstream>-better.<n>`. `upstream-sync` checks upstream daily: if none of the files above changed upstream it bumps the base and releases on its own, otherwise it opens a pull request with upstream's changes merged in, and merging that releases.
