"""
better-mealie: translates every scraped recipe into a fixed language.

Upstream only translates when the caller asks for it, and only on the AI import. Setting
BETTER_MEALIE_TRANSLATE_TO (e.g. "Danish") runs the same translation step on every URL import,
including recipes read straight from a page's structured data, which never reach the AI.
"""

import os
from collections.abc import Awaitable, Callable

from mealie.core.root_logger import get_logger
from mealie.lang.providers import Translator
from mealie.repos.repository_factory import AllRepositories
from mealie.schema.recipe import Recipe

TRANSLATE_TO_ENV = "BETTER_MEALIE_TRANSLATE_TO"

# the fields the translation step rewrites; everything else (image, url, nutrition, ...) is kept
TRANSLATED_FIELDS = [
    "name",
    "description",
    "recipe_yield",
    "recipe_yield_quantity",
    "recipe_servings",
    "total_time",
    "prep_time",
    "perform_time",
    "recipe_ingredient",
    "recipe_instructions",
    "notes",
]

logger = get_logger()


async def auto_translate(
    recipe: Recipe,
    repos: AllRepositories,
    translator: Translator,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
) -> Recipe:
    """Returns the recipe translated into BETTER_MEALIE_TRANSLATE_TO, or unchanged if that's unset or fails."""

    language = os.environ.get(TRANSLATE_TO_ENV, "").strip()
    if not language:
        return recipe

    from mealie.services.openai import OpenAIService
    from mealie.services.recipe.import_workflow.context import WorkflowContext, WorkflowInput, WorkflowOptions
    from mealie.services.recipe.import_workflow.steps.translate_recipe import TranslateRecipeStep

    ai = OpenAIService(repos)
    settings = ai.provider_settings
    if not (settings and settings.ai_enabled):
        logger.warning(f"{TRANSLATE_TO_ENV} is set but AI is not enabled for this group; not translating")
        return recipe

    ctx = WorkflowContext(
        input=WorkflowInput(url=recipe.org_url),
        options=WorkflowOptions(translate_language=language),
        repos=repos,
        translator=translator,
        ai=ai,
        on_progress=on_progress,
        draft_recipe=recipe,
    )

    step = TranslateRecipeStep()
    if not step.should_run(ctx):
        return recipe

    await ctx.report_progress(step.progress_key)
    try:
        await step.run(ctx)
    except Exception:
        # same policy as upstream's optional step: an untranslated recipe beats a failed import
        logger.exception(f"Translating recipe into {language} failed, keeping the original")
        return recipe

    translated = ctx.draft_recipe
    if translated is None or translated is recipe:
        return recipe

    logger.info(f"Translated recipe into {language}: {recipe.name!r} -> {translated.name!r}")
    return recipe.model_copy(update={field: getattr(translated, field) for field in TRANSLATED_FIELDS})
