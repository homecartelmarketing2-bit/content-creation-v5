# =====================================================================
#  AIRTABLE TABLE DEFINITIONS
#  Each entry maps a table name + ID to its blend prompt.
# =====================================================================

import re

_BLEND_TEMPLATE = (
    "Seamlessly integrate {fixtures} into this {room}. "
    "Remove or replace any existing lighting fixtures already in the scene "
    "(chandeliers, pendant lights, floor lamps, table lamps, wall lights, "
    "sconces, ceiling lights) — only the provided {fixtures} should appear "
    "as the lighting elements. Keep all other room furniture and decor intact. "
    "Ensure both fixtures are realistically scaled and proportionate to "
    "the room size and surrounding {surroundings}. Match the perspective, "
    "lighting, and shadows naturally so they appear as if originally part "
    "of the space."
)

_CHANDELIER_BLEND_PROMPT = (
    "Task: Seamlessly blend and install the chandelier from the 'Furniture Item' image into the 'Styled Photo' room scene. "
    "Guidelines: "
    "1. Existing Fixture Replacement: Carefully locate and remove any existing chandelier, pendant light, or ceiling fixture in the room backdrop. "
    "Replace it with the new chandelier in the exact same spatial coordinates, matching its scaling, height, and mounting placement. "
    "2. Scale and Proportions: Keep the scale of the chandelier realistic, elegant, and proportional to the room's height, sofa, tables, and architecture. "
    "Do not make the chandelier oversized or too large (i.e., prevent a bloated or giant appearance). "
    "3. Secure Ceiling Mounting (Anti-Floating): The chandelier must hang securely from the ceiling. If the ceiling is high, you must extend its rod, chain, or cord "
    "all the way up until it connects cleanly and naturally with the ceiling canopy or mounting box on the ceiling. There must be no gap between the ceiling and the rod/chain; "
    "the fixture must not appear to float or hang in mid-air. "
    "4. Lighting and Perspective Integration: Match the perspective angle of the chandelier to the room. Harmonize the lighting, reflections, shadows, "
    "and colors of the chandelier with the ambient light of the room interior, including soft shadows cast on the ceiling above."
)



def _parse_items(name: str) -> tuple[str, str]:
    """Splits a table name like 'Floor Lamp and Ceiling Mounted' into two item names."""
    parts = re.split(r'\s+and\s+|\s*\+\s*', name, maxsplit=1)
    item1 = parts[0].strip()
    item2 = parts[1].strip() if len(parts) > 1 else item1
    return item1, item2


def _table(name: str, table_id: str, fixtures: str,
           room: str = "room", surroundings: str = "furniture",
           blend_prompt: str = None) -> dict:
    """Helper to build a table entry with a consistent blend prompt."""
    item1, item2 = _parse_items(name)
    bp = blend_prompt or _BLEND_TEMPLATE.format(
        fixtures=fixtures, room=room, surroundings=surroundings
    )
    return {
        "name": name,   
        "id": table_id,
        "blend_prompt": bp,
        "item1": item1,
        "item2": item2 if table_id != "tblDDmCs4S2ePxIfQ" else "",
        "aspect_ratio": "3:4" if table_id == "tblDDmCs4S2ePxIfQ" else "9:16",
        "resolution": "1K" if table_id == "tblDDmCs4S2ePxIfQ" else "2K",
    }


AIRTABLE_TABLES = [
    # ── Floor Lamps ─────────────────────────────────────────────────
    # _table("Floor Lamp + Ceiling Mounted",             "tbl0H4CE8jdcawJfT", "a floor lamp and ceiling-mounted light"),

    # ── Chandeliers ─────────────────────────────────────────────────
    _table("Chandelier",                               "tblDDmCs4S2ePxIfQ", "a chandelier", blend_prompt=_CHANDELIER_BLEND_PROMPT),
]

# Field mappings for standard tables
DEFAULT_FIELD_MAPPING = {
    "Styled Photo Prompt": "Styled Photo Prompt",
    "Styled Photo": "Styled Photo",
    "Styled Photo URL": "Styled Photo URL",
    "Styled Photo Raw URL": "Styled Photo Raw URL",
    "Furniture Item": "Furniture Item",
    "Furniture Item2": "Furniture Item2",
    "Blended Image": "Blended Image",
    "Blended Image Raw URL": "Blended Image Raw URL",
    "Moodboard Image": "Moodboard Image",
    "Before Reels": "Before Reels",
    "After Reels": "After Reels",
    "Combine Video Before and After": "Combine Video Before and After",
    "Closeup Photo One": "Closeup Photo One",
    "Closeup Photo One Raw URL": "Closeup Photo One Raw URL",
    "Closeup Photo Two": "Closeup Photo Two",
    "Closeup Photo Two Raw URL": "Closeup Photo Two Raw URL",
    "Closeup Photo One Video": "Closeup Photo One Video",
    "Closeup Photo Two Video": "Closeup Photo Two Video",
    "Combine Video Closeups": "Combine Video Closeups",
    "CTA": "CTA",
    "Polls and Slider": "Polls and Slider",
    "Poll Question": "Poll Question",
    "Poll Choice A": "Poll Choice A",
    "Poll Choice B": "Poll Choice B",
    "Tips Reels": None,
    "Tips and Edu Feeds": None,
    "Tips and Edu Stories": None,
    "Before and After Feeds": None,
}

# Table-specific overrides
TABLE_FIELD_MAPPINGS = {
    "tblDDmCs4S2ePxIfQ": {
        "Reference Photo": "Reference Photo",
        "Room Interior": "Room Interior",
        "Styled Photo Prompt": "Styled Photo Prompt",
        "Styled Photo": "Room Interior",                # Generated room interior backdrop
        "Styled Photo URL": None,
        "Styled Photo Raw URL": None,
        "Furniture Item": "Furniture Item",
        "Furniture Item2": None,
        "Blended Image": "Blended Image",                # Blended room interior + Chandelier
        "Blended Image Raw URL": "Blended Image Raw URL",
        "Moodboard Image": "Moodboard",                  # Moodboard field
        "Before Reels": "Before Reels",
        "After Reels": "Styled Reels",                   # Styled Reels field

        "Combine Video Before and After": "Before and After Reels",
        "Closeup Photo One": "Product Closeup Feeds",
        "Closeup Photo One Raw URL": "Product Closeup One Raw URL",
        "Closeup Photo Two": "Product Closeup Feeds",
        "Closeup Photo Two Raw URL": "Product Closeup Two Raw URL",
        "Closeup Photo One Video": None,
        "Closeup Photo Two Video": None,
        "Combine Video Closeups": "Product Closeup Reels",
        "CTA": "CTA",
        "Polls and Slider": None,
        "Poll Question": None,
        "Poll Choice A": None,
        "Poll Choice B": None,
        "Tips Reels": "Tips Reels",
        "Tips and Edu Feeds": "Tips and Edu Feeds",
        "Tips and Edu Stories": "Tips and Edu Stories",
        "Before and After Feeds": "Before and After Feeds",
    }
}

