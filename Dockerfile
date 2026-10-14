FROM ghcr.io/mealie-recipes/mealie:v3.28.0

ARG SITE=/opt/mealie/lib/python3.14/site-packages/mealie
COPY mealie/services/openai/transcription.py ${SITE}/services/openai/transcription.py
COPY mealie/services/scraper/scraper_strategies.py ${SITE}/services/scraper/scraper_strategies.py
COPY mealie/services/scraper/scraper.py ${SITE}/services/scraper/scraper.py
COPY mealie/services/scraper/auto_translate.py ${SITE}/services/scraper/auto_translate.py
COPY mealie/services/recipe/import_workflow/compilers/transcription.py ${SITE}/services/recipe/import_workflow/compilers/transcription.py
COPY mealie/services/openai/prompts/recipes/translate-recipe.txt ${SITE}/services/openai/prompts/recipes/translate-recipe.txt
