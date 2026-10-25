FROM ghcr.io/mealie-recipes/mealie:v3.29.0

ARG SITE=/opt/mealie/lib/python3.14/site-packages/mealie
# COPY would silently create SITE if upstream moved to another Python; fail instead
RUN python -c "import mealie, os, sys; d = os.path.dirname(mealie.__file__); sys.exit(0 if d == '${SITE}' else f'mealie lives in {d}, not ${SITE}')"

COPY mealie/services/openai/transcription.py ${SITE}/services/openai/transcription.py
COPY mealie/services/scraper/scraper_strategies.py ${SITE}/services/scraper/scraper_strategies.py
COPY mealie/services/scraper/scraper.py ${SITE}/services/scraper/scraper.py
COPY mealie/services/scraper/auto_translate.py ${SITE}/services/scraper/auto_translate.py
COPY mealie/services/recipe/import_workflow/compilers/transcription.py ${SITE}/services/recipe/import_workflow/compilers/transcription.py
COPY mealie/services/openai/prompts/recipes/translate-recipe.txt ${SITE}/services/openai/prompts/recipes/translate-recipe.txt

# point duva and friends at this fork's releases, whose notes include upstream's
ARG VERSION=dev
LABEL org.opencontainers.image.title="better-mealie" \
      org.opencontainers.image.source="https://github.com/Miista/better-mealie" \
      org.opencontainers.image.url="https://github.com/Miista/better-mealie" \
      org.opencontainers.image.version="${VERSION}"
