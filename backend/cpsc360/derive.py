"""Automated derivations over source records. Pure functions; ingest.derive writes their output to `inference`."""

import re
from dataclasses import dataclass

NORM_METHOD = "keys-v2"
GENERIC_MODEL_MANUFACTURERS = 5
HAZARD_METHOD = "hazard-rules-v2"

_PLACEHOLDERS = {
    "unknown", "unk", "na", "n/a", "none", "no", "idk", "idontknow", "notsure", "unsure",
    "dontknow", "notknown", "notavailable", "nomodel", "nomodelnumber", "unknownmodel",
    "notapplicable", "redacted", "noidea", "cantremember", "notlisted", "various",
    "idonotknow", "donotknow", "unavailable", "notprovided", "noneprovided", "nonelisted",
    "seeabove", "seebelow", "seephoto", "seephotos", "seepicture", "seepictures", "vinredacted",
}
_MFR_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "ltd", "limited",
    "lp", "llp", "plc", "the", "usa", "us", "america", "americas", "na", "intl", "international",
}


def match_text(value: str | None) -> str:
    """Letters and digits only, lowercased: the form brand and model values are compared in."""
    return _alnum(value or "")


def _alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def manufacturer_key(name: str) -> str:
    """'SAMSUNG ELECTRONICS AMERICA, INC. (SEA)' and 'Samsung Electronics' -> 'samsung electronics'."""
    text = re.sub(r"\([^)]*\)", " ", name.lower())
    words = [w for w in re.split(r"[^a-z0-9&]+", text) if w and w not in _MFR_SUFFIXES]
    return " ".join(words) or name.strip().lower()


def brand_key(brand: str | None) -> str | None:
    key = _alnum(brand or "")
    return key if len(key) >= 2 and key not in _PLACEHOLDERS else None


def model_key(model: str | None) -> str | None:
    """Model numbers compare on letters and digits only. Placeholders and single characters never match.

    ingest.rebuild_inference also drops keys reported for many manufacturers, since those identify nothing.
    """
    key = _alnum(model or "")
    return key if len(key) >= 2 and key not in _PLACEHOLDERS else None


@dataclass(frozen=True)
class Hazard:
    key: str
    label: str
    pattern: re.Pattern[str]


def _rule(key: str, label: str, *phrases: str) -> Hazard:
    return Hazard(key, label, re.compile(r"\b(?:" + "|".join(phrases) + r")\b", re.IGNORECASE))


HAZARDS: list[Hazard] = [
    _rule("fire", "Fire", r"caught (?:on )?fire", r"on fire", r"fires?", r"flames?", r"flamed", r"ignit\w*", r"blaze"),
    _rule("overheating", "Overheating / melting", r"overheat\w*", r"too hot", r"hot to the touch", r"melt(?:ed|ing|s)?", r"scorch\w*", r"smok(?:e|ed|ing)", r"charred"),
    _rule("electrical", "Electrical shock / arcing", r"shock(?:ed|ing|s)?", r"electrocut\w*", r"spark(?:ed|ing|s)?", r"arc(?:ed|ing)", r"short(?:ed)? circuit\w*", r"exposed wires?"),
    _rule("burn", "Burn / scald", r"burn(?:s|ed|t)?", r"scald\w*", r"blister\w*"),
    _rule("shatter_explosion", "Shattering / explosion", r"shatter\w*", r"explo(?:de|ded|des|ding|sion|sions)", r"blew up", r"burst"),
    _rule("laceration", "Laceration / cut", r"lacerat\w*", r"stitch(?:es)?", r"gash\w*", r"sliced", r"sharp edges?", r"bleed\w*", r"bled", r"cut (?:my|his|her|their|our) \w+"),
    _rule("choking", "Choking / ingestion", r"chok(?:e|ed|es|ing)", r"swallow\w*", r"ingest\w*", r"aspirat\w*", r"small parts?"),
    _rule("suffocation", "Suffocation / strangulation", r"suffocat\w*", r"strangl\w*", r"asphyxia\w*", r"entangl\w*", r"around (?:his|her|the baby's|the child's) neck"),
    _rule("entrapment", "Entrapment / pinching / crushing", r"entrap\w*", r"trapped", r"pinch(?:ed|ing|es)?", r"crush(?:ed|ing)?", r"amputat\w*"),
    _rule("fall", "Fall", r"fell", r"falls?", r"falling", r"tripped", r"slipped"),
    _rule("tip_over", "Tip-over", r"tip(?:ped|s)? over", r"tipover", r"toppl\w*"),
    _rule("chemical", "Chemical / toxic exposure", r"toxic", r"fumes?", r"chemicals?", r"off[- ]?gas\w*", r"poison\w*", r"carbon monoxide", r"lead paint", r"lead content"),
    _rule("structural", "Structural / mechanical failure", r"collaps\w*", r"broke (?:off|apart|loose)", r"snapped", r"came apart", r"fell apart", r"detach\w*", r"came loose"),
    _rule("battery", "Battery failure", r"batter(?:y|ies) (?:swell\w*|swollen|leak\w*|overheat\w*|explod\w*|caught fire)", r"lithium", r"swollen batter(?:y|ies)"),
    _rule("drowning", "Drowning / submersion", r"drown\w*", r"submerg\w*"),
    _rule("skin_irritation", "Skin irritation / allergic reaction", r"rash(?:es)?", r"hives", r"irritat\w*", r"allergic reactions?", r"redness", r"itch(?:y|ing|es)?", r"dermatitis"),
]
HAZARD_LABELS = {hazard.key: hazard.label for hazard in HAZARDS}


def tag_hazards(narrative: str) -> dict[str, list[str]]:
    """Hazard key -> distinct matched phrases (lowercased, up to 5) found in the consumer narrative."""
    tags: dict[str, list[str]] = {}
    for hazard in HAZARDS:
        phrases = list(dict.fromkeys(m.group(0).lower() for m in hazard.pattern.finditer(narrative)))
        if phrases:
            tags[hazard.key] = phrases[:5]
    return tags
