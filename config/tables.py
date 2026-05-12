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


def _parse_items(name: str) -> tuple[str, str]:
    """Splits a table name like 'Floor Lamp and Ceiling Mounted' into two item names."""
    parts = re.split(r'\s+and\s+|\s*\+\s*', name, maxsplit=1)
    item1 = parts[0].strip()
    item2 = parts[1].strip() if len(parts) > 1 else item1
    return item1, item2


def _table(name: str, table_id: str, fixtures: str,
           room: str = "room", surroundings: str = "furniture") -> dict:
    """Helper to build a table entry with a consistent blend prompt."""
    item1, item2 = _parse_items(name)
    return {
        "name": name,   
        "id": table_id,
        "blend_prompt": _BLEND_TEMPLATE.format(
            fixtures=fixtures, room=room, surroundings=surroundings
        ),
        "item1": item1,
        "item2": item2,
    }


AIRTABLE_TABLES = [
    # ── Floor Lamps ─────────────────────────────────────────────────
    _table("Floor Lamp + Ceiling Mounted",             "tbl0H4CE8jdcawJfT", "a floor lamp and ceiling-mounted light"),
    _table("Floor Lamp + Chandelier",                  "tblUdcQhWKBbj2QG2", "a floor lamp and chandelier"),

    # ── Flush Ceiling Lights ────────────────────────────────────────
    _table("Flush Ceiling Lights + Wall Lights",       "tblYrmZTWRBzQnBFd", "a flush ceiling light and wall light"),
    _table("Flush Ceiling Lights + Table Lamps",       "tblYTf4qZJ6UHGAPN", "a flush ceiling light and table lamp"),
    _table("Flush Ceiling Lights + Floor Lamps",       "tblnvjkVkL0BpWfTR", "a flush ceiling light and floor lamp"),
    _table("Flush Ceiling Lights + Ceiling Fans",      "tbl34Yc69mjysWNcR", "a flush ceiling light and ceiling fan"),

    # ── Semi Ceiling Lights ─────────────────────────────────────────
    _table("Semi Ceiling Lights + Wall Lights",        "tblozD79qS5YuJXXv", "a semi ceiling light and wall light"),
    _table("Semi Ceiling Lights + Table Lamps",        "tblFbDpIVCKCX3Mpf", "a semi ceiling light and table lamp"),
    _table("Semi Ceiling Lights + Floor Lamps",        "tblbhmfLEjC62rOH6", "a semi ceiling light and floor lamp"),
    _table("Semi Ceiling Lights + Ceiling Fans",       "tblu7xSWdZDnfKKns", "a semi ceiling light and ceiling fan"),

    # ── Chandeliers ─────────────────────────────────────────────────
    _table("Chandelier + Wall Lights",                 "tblTL9xe4fLuAa96W", "a chandelier and wall light"),
    _table("Chandelier + Table Lamps",                 "tblvkeFCfcKYH9hPg", "a chandelier and table lamp"),
    _table("Chandelier + Floor Lamps",                 "tblpdaohkCjyypjZO", "a chandelier and floor lamp"),
    _table("Chandelier + Ceiling Fans",                "tbluxx64dOHxwNAoZ", "a chandelier and ceiling fan"),

    # ── Cluster Chandeliers ─────────────────────────────────────────
    _table("Cluster Chandelier + Wall Lights",         "tblWcWGHhaJBmxCSl", "a cluster chandelier and wall light"),
    _table("Cluster Chandelier + Table Lamps",         "tblvLVkVGaoKuVxCA", "a cluster chandelier and table lamp"),
    _table("Cluster Chandelier + Floor Lamps",         "tblVeh75sIJfIje07", "a cluster chandelier and floor lamp"),

    # ── Pendant Lights ──────────────────────────────────────────────
    _table("Pendant Lights + Wall Lights",             "tblBi9yHI2fEq7KTD", "a pendant light and wall light"),
    _table("Pendant Lights + Table Lamps",             "tblev1cIxtxBAlQ4o", "a pendant light and table lamp"),
    _table("Pendant Lights + Floor Lamps",             "tbl086DTyCgaKVe0j", "a pendant light and floor lamp"),
    _table("Pendant Lights + Ceiling Fans",            "tblO6akucuYJCs1gi", "a pendant light and ceiling fan"),

    # ── Bathroom ────────────────────────────────────────────────────
    _table("Bathroom Lights + Chandelier",             "tblbNOklr1NPwsoMO", "a bathroom light and chandelier", room="bathroom", surroundings="fixtures"),
    _table("Bathroom Lights + Pendant Light",          "tbloulRxtH5w4eG0p", "a bathroom light and pendant light", room="bathroom", surroundings="fixtures"),

    # ── Recessed Downlights ─────────────────────────────────────────
    _table("Recessed Downlights + Wall Lights",        "tbl2hlWxUic2aAO9L", "a recessed downlight and wall light"),
    _table("Recessed Downlights + Table Lamps",        "tblRpsdzwsTso11n2", "a recessed downlight and table lamp"),
    _table("Recessed Downlights + Floor Lamps",        "tblcssYpSoEZJMQrK", "a recessed downlight and floor lamp"),

    # ── Surface Mounted Lights ──────────────────────────────────────
    _table("Surface Mounted Lights + Wall Lights",     "tblwZcrfrUPi9SHWq", "a surface mounted light and wall light"),
    _table("Surface Mounted Lights + Table Lamps",     "tbl4vkGvZAzBdwE7d", "a surface mounted light and table lamp"),
    _table("Surface Mounted Lights + Floor Lamps",     "tblHS1erdQXIpdopH", "a surface mounted light and floor lamp"),

    # ── Track Lights ────────────────────────────────────────────────
    _table("Track Lights + Wall Lights",               "tble1PuyKD5S8We9A", "a track light and wall light"),
    _table("Track Lights + Table Lamps",               "tblOFT0aTZfVKMIIn", "a track light and table lamp"),
    _table("Track Lights + Floor Lamps",               "tblJMHEITVogB6pK3", "a track light and floor lamp"),

    # ── Linear Lights ───────────────────────────────────────────────
    _table("Linear Lights + Wall Lights",              "tblgSB1SdpCFBUe1q", "a linear light and wall light"),
    _table("Linear Lights + Table Lamps",              "tblV1JO9UsRauQ4Hh", "a linear light and table lamp"),
    _table("Linear Lights + Floor Lamps",              "tbl9J22NPIX1ARSuY", "a linear light and floor lamp"),

    # ── Spot Lights ─────────────────────────────────────────────────
    _table("Spot Lights + Wall Lights",                "tblwWfWz2XoharxTb", "a spot light and wall light"),
    _table("Spot Lights + Table Lamps",                "tblw1y9ajOnBdYdLF", "a spot light and table lamp"),
    _table("Spot Lights + Floor Lamps",                "tblL8LAC07y1qZZeU", "a spot light and floor lamp"),

    # ── Magnetic Lights ─────────────────────────────────────────────
    _table("Magnetic Lights + Wall Lights",            "tbl721iQ4LZ1iob8J", "a magnetic light and wall light"),
    _table("Magnetic Lights + Table Lamps",            "tblUMapHFRkywBEN7", "a magnetic light and table lamp"),
    _table("Magnetic Lights + Floor Lamps",            "tblgtBnqSjFGu8mB1", "a magnetic light and floor lamp"),

    # ── Indoor Step Lights ──────────────────────────────────────────
    _table("Indoor Step Lights + Wall Lights",         "tblnxwIg8HJlPbP3t", "an indoor step light and wall light"),
    _table("Indoor Step Lights + Floor Lamps",         "tbltWbDvi5An8wPA7", "an indoor step light and floor lamp"),

    # ── Multi-Functional Lights ─────────────────────────────────────
    _table("Multi-Functional Lights + Wall Lights",    "tblqZoYq12diG1gqy", "a multi-functional light and wall light"),
    _table("Multi-Functional Lights + Table Lamps",    "tbl2mVFXAy2mu2cW6", "a multi-functional light and table lamp"),
    _table("Multi-Functional Lights + Floor Lamps",    "tblgukIaeBt3sxGlW", "a multi-functional light and floor lamp"),

    # ── Ceiling Fans ────────────────────────────────────────────────
    _table("Lighted Ceiling Fans + Wall Lights",       "tblygqSjv5iJngsYO", "a lighted ceiling fan and wall light"),
    _table("Lighted Ceiling Fans + Table Lamps",       "tblXIypYZQi800FPK", "a lighted ceiling fan and table lamp"),
    _table("Lighted Ceiling Fans + Floor Lamps",       "tble6pPlSXkrbUbuT", "a lighted ceiling fan and floor lamp"),
    
    _table("Standard Ceiling Fans + Wall Lights",      "tblCDpC6mjPkNE2qm", "a standard ceiling fan and wall light"),
    _table("Standard Ceiling Fans + Table Lamps",      "tblhOQV8rd04R8Kds", "a standard ceiling fan and table lamp"),

    _table("Low Profile Ceiling Fans + Wall Lights",   "tblG8jZ8x4gzbdS5O", "a low profile ceiling fan and wall light"),
    _table("Low Profile Ceiling Fans + Table Lamps",   "tbluOm6185mpfGCJe", "a low profile ceiling fan and table lamp"),

    _table("Big Ceiling Fans + Wall Lights",           "tblMU9eaaNISVyThb", "a big ceiling fan and wall light"),
    _table("Big Ceiling Fans + Floor Lamps",           "tbl8C4QiIe5NyrQ5n", "a big ceiling fan and floor lamp"),

    _table("Three Blade Ceiling Fans + Wall Lights",   "tblvYfvC75ueZynkU", "a three blade ceiling fan and wall light"),
    _table("Four Blade Ceiling Fans + Wall Lights",    "tblXy4xG1hWh3DVmv", "a four blade ceiling fan and wall light"),
    _table("Five Blade Ceiling Fans + Wall Lights",    "tbl3rHBdof3Ae5bEa", "a five blade ceiling fan and wall light"),

    _table("Outdoor Ceiling Fans + Wall Lights",       "tblhAvYJruJvWcunM", "an outdoor ceiling fan and wall light", room="outdoor space", surroundings="exterior elements"),
    _table("Outdoor Ceiling Fans + Floor Lamps",       "tbll0cTrCDg1SiTB9", "an outdoor ceiling fan and floor lamp", room="outdoor space", surroundings="exterior elements"),
]
