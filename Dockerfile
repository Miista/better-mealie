FROM ghcr.io/mealie-recipes/mealie:v3.20.1

COPY mealie/services/scraper/scraper_strategies.py /opt/mealie/lib/python3.12/site-packages/mealie/services/scraper/scraper_strategies.py
COPY mealie/services/openai/prompts/recipes/parse-recipe-video.txt /opt/mealie/lib/python3.12/site-packages/mealie/services/openai/prompts/recipes/parse-recipe-video.txt
COPY mealie/services/openai/prompts/recipes/scrape-recipe.txt /opt/mealie/lib/python3.12/site-packages/mealie/services/openai/prompts/recipes/scrape-recipe.txt
COPY mealie/services/openai/prompts/recipes/parse-recipe-image.txt /opt/mealie/lib/python3.12/site-packages/mealie/services/openai/prompts/recipes/parse-recipe-image.txt
