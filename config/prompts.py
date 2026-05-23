# =====================================================================
#  PROMPTS & CREATIVE VARIATIONS
# =====================================================================

# ── Video Prompts ───────────────────────────────────────────────────
BEFORE_REELS_PROMPT = "Slowly Rotating Around Camera Movement"
AFTER_REELS_PROMPT = "Slowly Rotating Around Camera Movement"
CLOSEUP_VIDEO_PROMPT = "Slowly Rotating Around Camera Movement"

# ── Music Prompt (Suno) ────────────────────────────────────────────
# Kept short and grounded so Suno renders a realistic, listenable track
# instead of stacking too many genre cues. Focuses on actual instruments
# and a clear mood rather than marketing adjectives.
MUSIC_PROMPT = (
    "Upbeat luxury commercial background music. Warm acoustic guitar, "
    "soft elegant piano, and a gentle inspiring modern pop beat. Clean, "
    "sophisticated atmosphere for high-end home decor and interior design marketing. "
    "Instrumental only, clean mix, no vocals."
)


# ── Closeup Photo Prompt ──────────────────────────────────────────
CLOSEUP_PROMPT_TEMPLATE = (
    "Generate me a medium closeup photo of {item}, "
    "maintain the appearance of the item as is"
)

PRODUCT_CLOSEUP_FEEDS_PROMPT = "Use the first image strictly as a layout, composition, and crop reference. Extract the product (chandelier) from the second image and place it seamlessly into this exact layout style on a pure plain white background. [{caption}]"

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
    "You are a faithful image-to-text interior scene writer for a local vision-language model.\n"
    "Your task is to look at the uploaded reference photo and output a compact, accurate "
    "description of the SAME room in exactly ONE sentence.\n\n"

    "<TOP_PRIORITY_RULE>\n"
    "NEVER mention any electric lighting or lighting fixture under any circumstance, even if "
    "one is clearly visible in the photo.\n"
    "Forbidden objects and words include: lamp, lamps, chandelier, pendant light, ceiling light, bulb, sconce, spotlight, track light, lantern, fan light, ceiling fan, fixture, lighting, illuminated, glowing.\n"
    "If any such object appears in the image, completely ignore it as if it does not exist — describe everything else faithfully but leave the lighting out.\n"
    "</TOP_PRIORITY_RULE>\n\n"

    "<SCENE_POLICY>\n"
    "Describe the actual room shown in the image as accurately as possible: keep its real "
    "wall colors, flooring, furniture, materials, layout, perspective, and overall mood.\n"
    "Do NOT invent a different room and do NOT change the style of the space — stay true to "
    "what the photo shows, only omitting the lighting.\n"
    "Do not invent people, animals, text, brands, reflections, mirrors, electronics, or appliances that are not actually present in the photo.\n"
    "</SCENE_POLICY>\n\n"

    "<ALLOWED_DETAILS>\n"
    "Describe what you actually see, focusing on:\n"
    "- room type\n"
    "- wall color and finish\n"
    "- floor color and material\n"
    "- the real furniture pieces and their placement\n"
    "- decor, textiles, plants, rugs, and materials that are genuinely visible\n"
    "- ceiling appearance\n"
    "- window daylight or sunlight\n"
    "- the room's actual color palette and atmosphere\n"
    "</ALLOWED_DETAILS>\n\n"

    "<STYLE_RULES>\n"
    "Keep the tone visual, clean, and realistic — describe the photo, do not embellish it.\n"
    "Describe daylight and natural light only (e.g. soft daylight, warm sunlight, diffused "
    "daylight); never describe artificial light sources.\n"
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
    "2. The description matches the actual room in the photo (same colors, furniture, layout).\n"
    "3. Nothing was invented that is not visible in the photo.\n"
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


def build_vision_user_prompt(style: str = "", mood: str = "") -> str:
    """Builds the user-facing prompt sent alongside the reference image.

    Faithful mode: the prompt describes the ACTUAL room in the reference
    photo (real colors, furniture, layout, perspective, atmosphere) and
    only omits any lighting. The ``style`` / ``mood`` arguments are kept
    for backward compatibility but are no longer injected so the output
    stays true to the photo.
    """
    return (
        "Look at the reference photo and generate exactly ONE sentence that "
        "accurately describes the SAME interior scene shown in it.\n\n"
        "Capture the room's real wall colors, flooring, furniture, materials, "
        "decor, layout, perspective, and overall mood as faithfully as "
        "possible. Do not invent a different room.\n\n"
        "REMINDER: Leave out ALL lighting and fixtures entirely — no lamps, "
        "chandeliers, pendants, ceiling lights, or fans, even if they appear "
        "in the photo. Describe natural daylight only.\n\n"
        "Output ONLY the plain text sentence now."
    )


# ── Poll Phase (Phase 13) ──────────────────────────────────────────
# System prompt steering the LLM to emit a strict JSON object containing
# a poll question + two short A/B answer choices. This is a text-only
# call (no reference image is sent) — the LLM uses the lighting/room
# context that the pipeline supplies as the user prompt.
POLL_VISION_SYSTEM_PROMPT = (
    "You are a social-media copywriter for an interior-design marketing brand.\n"
    "Write a SHORT, fun, engaging poll question with exactly two answer "
    "choices (A and B) that an Instagram / Facebook audience would enjoy "
    "voting on.\n\n"
    "<TOPIC_RULES>\n"
    "- The poll must be relevant to interior design, home decor, lighting, "
    "furniture, room ambiance, or lifestyle aesthetics.\n"
    "- When room or fixture context is provided, the poll should feel "
    "inspired by it (without naming specific brands or products).\n"
    "- The two choices must be DIFFERENT, comparable, and short (1-4 words each).\n"
    "- The question must be a complete sentence ending with a question mark.\n"
    "- Keep the tone friendly, casual, and inviting. No hashtags. No emojis.\n"
    "- Do NOT name specific brands, products, or people.\n"
    "- Vary the topic between polls (lighting mood, color palette, furniture "
    "style, atmosphere, materials, etc.) so a series of polls feels fresh.\n"
    "</TOPIC_RULES>\n\n"
    "<LENGTH_RULES>\n"
    "- question: max 80 characters.\n"
    "- choice_a: max 24 characters.\n"
    "- choice_b: max 24 characters.\n"
    "</LENGTH_RULES>\n\n"
    "<OUTPUT_RULES>\n"
    "Return ONE single JSON object on a single line with EXACTLY these keys:\n"
    '{"question": "...", "choice_a": "...", "choice_b": "..."}\n'
    "No preface. No explanation. No markdown fences. No trailing text.\n"
    "</OUTPUT_RULES>"
)


def build_poll_user_prompt(context: str = "") -> str:
    """Builds the per-row user prompt with optional lighting/room context."""
    context = (context or "").strip()
    if context:
        return (
            "Generate ONE interior-design poll for this context:\n"
            f"{context}\n\n"
            "Return ONLY the JSON object on a single line."
        )
    return (
        "Generate ONE interior-design poll question and two short A/B "
        "answer choices. Return ONLY the JSON object on a single line."
    )

# Prompt template for nano-banana-pro that renders the final poll
# graphic. Placeholders {question} / {choice_a} / {choice_b} are filled
# with the LLM-generated copy. The layout itself is fixed and intended
# to match the reference poll-card design (centered dark card with two
# pill buttons, lettered circles on the left, on a soft fabric backdrop).
POLL_IMAGE_PROMPT_TEMPLATE = (
    "A clean modern vertical 9:16 social-media poll graphic, "
    "1080x1920 pixels, magazine-quality minimalist design.\n\n"

    "BACKGROUND:\n"
    "A soft, slightly-wrinkled warm off-white textile or paper surface "
    "filling the entire frame, lit by gentle natural daylight from the "
    "upper-left producing soft diffused shadows and a subtle, calm, "
    "tactile texture. No props, no furniture, no fixtures, no people, "
    "no hands.\n\n"

    "CARD (centered in the middle of the frame):\n"
    "A single rounded-corner panel with a dark charcoal-gray fill "
    "(approx #3a3a3a), corner radius around 28px, a subtle soft drop "
    "shadow, and generous internal padding. The card width spans about "
    "60% of the image width and is vertically centered around the "
    "middle of the composition. Nothing else floats outside of this card.\n\n"

    "CARD CONTENT (top to bottom, with equal padding on all sides):\n"
    "1) A bold white sans-serif question text, centered horizontally, "
    "tight line spacing, allowed to wrap across 2-3 lines, exact "
    "wording: \"{question}\"\n"
    "2) A small vertical gap below the question.\n"
    "3) Two horizontally-oriented pill-shaped buttons stacked vertically "
    "with a small gap between them. Each pill is a light off-white "
    "rounded rectangle (corner radius equal to half its height, so it "
    "looks like a pill). Each pill is anchored against the left and "
    "right inner edges of the dark card (matching the card's internal "
    "padding).\n"
    "4) On the LEFT side of each pill sits a solid dark charcoal-gray "
    "circle slightly smaller than the pill height, containing a bold "
    "white letter centered inside it: \"A\" in the top pill, \"B\" in "
    "the bottom pill.\n"
    "5) To the right of the circle, inside the pill, a medium dark-gray "
    "sans-serif label is left-aligned, vertically centered.\n"
    "   - Top pill label text (exact wording): \"{choice_a}\"\n"
    "   - Bottom pill label text (exact wording): \"{choice_b}\"\n\n"

    "STRICT REQUIREMENTS:\n"
    "- Render the text exactly as specified, with correct spelling, "
    "casing, and punctuation.\n"
    "- The card and its two pill buttons are the ONLY graphical "
    "elements in the frame. Everything else outside the card is the "
    "plain fabric/paper background.\n"
    "- Do NOT add any extra text, watermarks, logos, brand names, "
    "signatures, hashtags, emojis, captions, headings, footers, "
    "decorative lines, icons, or progress bars anywhere on the image.\n"
    "- Do NOT show any furniture, lighting fixtures, room scenes, "
    "hands, people, or product mockups."
)
