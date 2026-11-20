"""Arrival-time mechanism screens derived from hazards in pre-2024 archived notices.

The notice IDs document the source for each product/failure relationship.
A consumer must describe the event in the incident narrative. Product identity
may also come from the product description or the published product category.
"""
import re


def close(one, other, distance=65):
    gap = rf"[^.!?]{{0,{distance}}}"
    return rf"(?:{one}){gap}(?:{other})|(?:{other}){gap}(?:{one})"


RELEASE = r"came off|fell off|broke off|came loose|detach(?:ed)?|separat(?:ed)?|fell apart|dislodged"
ACTIVATION = r"turn(?:ed|s|ing)? on|switch(?:ed|es)? on|start(?:ed|s)?|activat(?:ed|es)"
SPONTANEOUS = r"on (?:its|their) own|by itself|unexpectedly|with ?out (?:touching|pressing)|unattended"

# ID, name, product context, required narrative evidence.
PATTERNS = [
    ('22059', 'unexpected power or failed shutoff',
     r"switch|power tool|saw|trimmer|range|cooktop|stove|oven|burner|mower|heater|microwave|blender|mixer",
     close(ACTIVATION, SPONTANEOUS, 36) + r"|(?:wouldn.t|would not|couldn.t|could not|failed to) (?:shut|turn|switch) off|kept running after"),
    ('24049', 'child product sheds a small part',
     r"infant|toy|child|toddler|baby|rattle|figure|teeth(?:er|ing)|plush|doll",
     close(r"\b(?:piece|button|eye|eyes|bead|head|peg|bell|wheel|magnet|ball|label|stem|part)s?\b", RELEASE, 36)),
    ('24068', 'support collapses beneath user',
     r"chair|stool|seat|bench|hammock|bed|bunk|ladder|table",
     close(r"sat|sitting|seated|standing|using|laying|under (?:me|him|her)|on it", r"collaps\w*|gave way|buckled|snapped|leg broke")),
    ('22111', 'detector silent during exposure',
     r"detector|smoke alarm|carbon monoxide alarm",
     close(r"smoke|fire|carbon monoxide|\bco\b|gas", r"didn.t|did not|failed to|never|no alarm|stayed silent",65),
     r"sound|alarm|alert|warn|detect|silent"),
    ('23290', 'infant airway compromised in sleep product',
     r"bassinet|sleep(?:er|ing pad)|cradle|infant swing|baby swing|lounger",
     close(r"roll(?:ed|ing)|slid|slipp?ed|face down|face.?first|wedged",r"face|suffocat|breath|trapped|stomach|chin")),
    ('23263', 'head or neck trapped in opening',
     r"rail|bed|gate|crib|ladder|play.?yard|spindle|bunk|walker",
     close(r"\b(?:head|neck|throat)\b",r"wedged|stuck|trapped|caught between|entrapped|strangl",40)),
    ('15183', 'product fragments mixed into food',
     r"appliance|blender|chopper|ice maker|ice dispenser|mix(?:er|ing)|processor|refrigerator|grinder|froth",
     close(r"metal|plastic|shard|fragment|broken piece|glass",r"in (?:the |my |our )?(?:food|ice|drink|mouth|soup|smoothie)|mixed (?:up )?in|swallow|chok|dispensed",70)),
    ('22215', 'finger caught in moving joint',
     r"stroller|folding|hinge|generator|brake|foldable|lounger",
     close(r"finger|fingertip|thumb",r"caught|trapped|pinched|crushed|amputat|severed")),
    ('24030', 'pressurized component ejected',
     r"compressed|pressure|tank|pump|cylinder|canister|inflator",
     close(r"cap|connector|fitting|valve|gauge|nozzle",r"flew|shot off|ejected|blew off|propelled|became a projectile")),
    ('23275', 'gas leaking at appliance connection',
     r"gas|propane",
     close(r"connector|connection|regulator|valve|hose",r"gas leak|leaking gas|propane leak|gas escap|gas pouring|smell(?:ed)? gas")),
    ('21068', 'cookware handle separates',
     r"cookware|saucepan|frying pan|skillet|kettle|coffee pot|stockpot",
     close(r"handle|latch",RELEASE + r"|snapped|broke",40)),
]
_COMPILED = [(name, re.compile(context), tuple(re.compile(p) for p in evidence))
             for _,name,context,*evidence in PATTERNS]


def prior_patterns(row) -> set[str]:
    story = " ".join((row.get("incident_description") or "").lower().replace("’", "'").split())
    context = " ".join((row.get("product_type") or "", row.get("product_description") or "", story)).lower()
    return {name for name, product, evidence in _COMPILED
            if product.search(context) and all(pattern.search(story) for pattern in evidence)}
