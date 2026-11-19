"""Brand-blind, pre-2024 list of CPSC recall mechanisms for the watchlist.

Candidate families came from the request. Three have a qualifying recall in the
supplied ledger. Range knobs accidentally activated by physical contact had no
matching pre-cutoff hazard in that ledger and are excluded.
"""

import re
from collections.abc import Mapping


def nearby(left: str, right: str) -> re.Pattern[str]:
    """Either order, at most 75 intervening characters within one sentence."""
    gap = r"[^.!?]{0,75}"
    return re.compile(rf"\b(?:{left})\b{gap}\b(?:{right})\b|\b(?:{right})\b{gap}\b(?:{left})\b")


# Recall 12-194, 2012-06-07. A selector can release the weight plates.
DUMBBELL = re.compile(r"\bdumb[ -]?bells?\b")
PLATE_RELEASE = nearby(
    r"(?:weight )?plates?|weights?",
    r"fell|falls?|falling|detach(?:ed|es|ing)?|separat(?:e|ed|es|ing)|dislodg(?:e|ed|es)|"
    r"(?:came|come|flew|slid|slipped|dropped) (?:off|out)",
)

# Recalls 21-035 (2020-11-24) and 23-256 (2023-08-10).
COOKER = re.compile(r"\b(?:pressure[ -]?cook(?:er|ing)s?|multi[ -]?cookers?)\b")
LID_RELEASE = nearby(
    r"lids?|covers?",
    r"(?:flew|blown|blew|popped|shot|came|blew right) off|"
    r"eject(?:ed|s|ing)?|detach(?:ed|es|ing)?|explod(?:e|ed|es)|blasted off",
)
CONTENTS_EJECTION = nearby(
    r"contents|foods?|liquids?|water|soups?|broth|sauce",
    r"eject(?:ed|s|ing)?|expel(?:led|s|ling)?|splash(?:ed|es|ing)?|"
    r"spray(?:ed|s|ing)?|spew(?:ed|s|ing)?|erupt(?:ed|s|ing)?|shot out",
)

# Recall 13-071, 2012-12-17. Swallowed expanding toy obstructs the bowel.
BEAD = re.compile(r"\b(?:water|gel|hydrogel|expand(?:ing|able)|water[ -]absorbing)[ -]?beads?\b")
INGESTION = re.compile(r"\b(?:swallow\w*|ingest\w*|ate|eaten)\b")
BLOCKAGE = nearby(r"intestin(?:e|es|al)|bowel", r"obstruct\w*|block\w*")


def known_mechanism(row: Mapping[str, str | None]) -> bool:
    story = " ".join((row["incident_description"] or "").casefold().split())
    product = " ".join((row[key] or "") for key in ("product_type", "product_description"))
    context = product.casefold() + " " + story
    return bool(
        (DUMBBELL.search(context) and PLATE_RELEASE.search(story))
        or (COOKER.search(context) and (LID_RELEASE.search(story) or CONTENTS_EJECTION.search(story)))
        or (BEAD.search(context) and INGESTION.search(story) and BLOCKAGE.search(story))
    )
