# =====================================================================
#  PROMPTS & CREATIVE VARIATIONS
# =====================================================================

# ── Video Prompts ───────────────────────────────────────────────────
BEFORE_REELS_PROMPT = "Slowly Rotating Around Camera Movement"
AFTER_REELS_PROMPT = "Slowly Rotating Around Camera Movement"
CLOSEUP_VIDEO_PROMPT = "Slowly Rotating Around Camera Movement"

# ── Closeup Photo Prompt ──────────────────────────────────────────
CLOSEUP_PROMPT_TEMPLATE = (
    "Generate me a medium closeup photo of {item}, "
    "maintain the appearance of the item as is"
)

# ── Moodboard Prompt ────────────────────────────────────────────────
MOODBOARD_PROMPT = (
    "Create a vertical professional interior design moodboard collage "
    "in a 3:4 aspect ratio featuring the main furniture and lighting "
    "fixtures visible in the reference image.\n\n"
    "Action: Isolate the items and arrange them in a clean flat-lay "
    "composition. Remove the original room background.\n\n"
    "Layout Style:\n\n"
    "Background: Solid cream or off-white paper texture.\n"
    "Composition: Vertical layout suitable for a 3:4 frame. Layer the "
    "furniture over abstract organic wavy shapes and 'blobs' in colors "
    "derived from the furniture materials.\n"
    "Elements: Include a vertical color palette strip on the right side "
    "and circular material texture swatches.\n"
    "Vibe: Retro-modern graphic design, stylish curation.\n"
    "Technical Specs: Vertical 3:4 aspect ratio, 4k resolution, "
    "photorealistic textures, soft lighting.\n\n"
    "STRICT RULE — NO TEXT: The final image must be purely visual. "
    "Do NOT render any text, letters, numbers, words, labels, captions, "
    "titles, headings, watermarks, signatures, logos, brand names, "
    "handwriting, or typography of any kind anywhere in the image. "
    "The color palette strip and texture swatches must be plain colored "
    "shapes only, with absolutely no written labels or annotations."
)

# ── Vision LLM System Prompt ───────────────────────────────────────
VISION_LLM_SYSTEM_PROMPT = (
    "You are a strict image-to-text interior scene writer for a local vision-language model.\n"
    "Your task is to output a compact interior description in exactly ONE sentence.\n\n"

    "<TOP_PRIORITY_RULE>\n"
    "NEVER mention any electric lighting or lighting fixture under any circumstance.\n"
    "Forbidden objects and words include: lamp, lamps, chandelier, pendant light, ceiling light, bulb, sconce, spotlight, track light, lantern, fan light, ceiling fan, fixture, lighting, illuminated, glowing.\n"
    "If any such object appears in the image, you must completely ignore it as if it does not exist.\n"
    "</TOP_PRIORITY_RULE>\n\n"

    "<SCENE_POLICY>\n"
    "Create a new believable interior scene inspired only by the room structure, furniture placement, and general layout of the image.\n"
    "Do not accurately describe the uploaded image.\n"
    "Do not mention décor that is not clearly necessary.\n"
    "Do not invent people, animals, text, brands, reflections, mirrors, electronics, or appliances unless essential to the room type.\n"
    "</SCENE_POLICY>\n\n"

    "<ALLOWED_DETAILS>\n"
    "You may describe only:\n"
    "- room type\n"
    "- wall color\n"
    "- floor color and material\n"
    "- ceiling appearance only as bare/plain/smooth if needed\n"
    "- window daylight or sunlight\n"
    "- simple non-electric furniture\n"
    "- fabric/material textures\n"
    "- overall natural atmosphere\n"
    "</ALLOWED_DETAILS>\n\n"

    "<STYLE_RULES>\n"
    "Keep the tone visual, clean, and realistic.\n"
    "Use natural sunlight only: morning sunlight, soft daylight, warm sunlight, diffused sunlight, indirect daylight.\n"
    "Keep walls and ceiling bare, plain, and free of decorations or mounted objects.\n"
    "Do not use poetic language.\n"
    "Do not use lists.\n"
    "Do not use markdown.\n"
    "</STYLE_RULES>\n\n"

    "<OUTPUT_RULES>\n"
    "Output exactly ONE plain sentence.\n"
    "No preface.\n"
    "No explanation.\n"
    "No labels.\n"
    "No bullet points.\n"
    "Maximum 320 characters.\n"
    "</OUTPUT_RULES>\n\n"

    "<SELF_CHECK>\n"
    "Before answering, silently verify:\n"
    "1. The sentence contains no forbidden lighting words.\n"
    "2. The scene is indoors.\n"
    "3. The sentence mentions only allowed details.\n"
    "4. The sentence is exactly one sentence.\n"
    "</SELF_CHECK>"
)
# ── Style & Mood Pools (picked randomly per generation) ────────────
STYLE_VARIATIONS = [
    "modern minimalist", "mid-century modern", "Scandinavian hygge",
    "industrial loft", "bohemian eclectic", "art deco glamour",
    "Japanese wabi-sabi", "coastal Mediterranean", "rustic farmhouse",
    "contemporary luxury", "retro 70s", "neo-classical",
    "tropical resort", "urban chic", "French provincial",
    "desert modern", "biophilic green", "maximalist bold",
    "transitional elegance", "Hollywood regency",
]

MOOD_VARIATIONS = [
    "warm and inviting", "cool and serene", "dramatic and moody",
    "bright and airy", "cozy and comfortable", "sleek and sophisticated",
    "earthy and organic", "vibrant and energetic", "soft and elegant",
    "bold and striking", "peaceful and zen", "opulent and rich",
]


def build_vision_user_prompt(style: str, mood: str) -> str:
    """Builds the user-facing prompt sent alongside the reference image."""
    return (
        f"Generate exactly ONE sentence describing a new interior design scene.\n\n"
        f"Target Style: {style}\n"
        f"Target Mood: {mood}\n\n"
        f"REMINDER: Your scene must have ZERO electrical lighting! "
        f"Ensure walls, ceilings, and tables are completely bare of any lamps or fixtures. "
        f"Output ONLY the plain text sentence now."
    )
