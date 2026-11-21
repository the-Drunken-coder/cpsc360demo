"""Exploratory brand-blind signals for ranking public incident reports.

Each predicate requires product or component evidence and supporting incident
language. Severity, model, serial, maker, comments and notice text are unused.
"""
import re

# Deliberately exclude generic phrases like "fire hazard" and "could cause a fire".
IGNITION = (r"caught (?:on )?fire|catch(?:ing)? (?:on )?fire|on fire|"
            r"(?:shooting|emitting|noticed|saw|open|visible) flames|"
            r"went up in flames|spontaneously combusted|smoking and flaming|"
            r"exploded|blew up|charred|scorch(?:ed|ing)?")
BATTERY = r"\bbatter(?:y|ies)\b|power ?bank|cordless|rechargeable|lithium"
CHILD = r"\b(?:infant|baby|babies|toddler|child|children|kid|kids|toy|toys|stroller)\b"

# Context can come from the description, product type, or incident. Failure
# evidence must come from the incident narrative. Allow consumer spellings.
FAMILIES = (
    ("battery ignition during charging",
     BATTERY, r"\bcharg(?:ing|er|ed)\b", IGNITION),
    ("portable battery fire",
     r"power ?bank|portable charg|battery (?:pack|charger)|battery chargers?/adapters",
     IGNITION),
    ("yard equipment fire or battery smoke",
     r"\b(?:mowers?|mowing|leaf blower|hedge trimmer|chain ?saw)\b",
     IGNITION + r"|(?:filled with|emitting|white|black) smoke"),
    ("water in powered equipment",
     r"pool (?:cleaner|vacuum)|underwater (?:scooter|camera)|submersible",
     r"water (?:intrusion|ingress|leaked|entered)|corrosion",
     r"batter(?:y|ies)|circuit"),
    ("compact refrigerator ignition",
     r"mini[ -]?(?:fridge|refrigerator)|desktop (?:fridge|refrigerator)|personal (?:beauty )?fridge",
     IGNITION),
    ("candle holder or candle body burns",
     r"candles?|candlesticks?|menorah|candelabra",
     r"caught (?:on )?fire|catch on fire|went up in flames|singed|scorch(?:ed|ing)?|char marks"),
    ("hose or fitting bursts",
     r"garden hose|expandable hose|pressure washer",
     r"\bburst\b(?![ -]?proof)|\bexploded\b|projectile|propell(?:ing|ed)|explosively separated"),
    ("steam escapes from fitting",
     r"steam (?:cleaner|cleaning|mop|iron)|garment steamer",
     r"nozzle|attachment|tubing|connection|hose",
     r"burn(?:ed|t|s)?|scald(?:ed|s)?|unexpectedly|detach(?:ed|es)?"),
    ("child-resistant feature missing",
     r"lighter|torch|lidocaine|ointment|medicat(?:ion|ed)|chemical",
     r"(?:lacks?|without|no |not |missing|did not have).{0,30}child[ -]?(?:proof|resistan|safety)"),
    ("child access to button battery",
     CHILD + r"|writing tablet|drawing tablet",
     r"(?:button|coin)[ -]?(?:cell|batter)",
     r"dislodged|missing|popp?ed out|pop out|swallow|came (?:out|loose)|easily (?:opened|removed)|no screw"),
    ("lead contamination of child product",
     CHILD + r"|hair clips?",
     r"(?:contaminat\w*|test\w*|ppm|positive|detected|paint|level\w*).{0,70}\blead\b|\blead\b.{0,60}(?:ppm|contaminat|paint|level|detected|positive)"),
    ("craft resin contact injury",
     r"\bresin\b", r"blister|irritat|burn(?:ed|s)?|sore throat|rash"),
    ("child restraint or support fails",
     r"baby gat[eE]|retractable gate|baby walker|high chair|step[ -]?stool|toddler tower|learning tower|bath seat",
     r"wedg(?:ed|ing)|(?:tip|flipp?)(?:ped|s)? (?:over|up)|\bflip\b|(?:bar|frame|leg|seat|strap).{0,45}(?:broke|snap|detach|came loose|collaps)|suction cups? (?:came loose|failed)"),
    ("guard allows finger contact",
     r"fan|blender|grinder|shredder",
     r"finger|thumb", r"stick(?:ing)?|reached|through|guard|opening|inside",
     r"cut|bleed|lacerat|amputat"),
    ("load-bearing grip releases",
     r"grab bar|safety bar|tub bar|hand ?rail|support rail",
     r"loss of grip|(?:bar|rail).{0,45}(?:releas|separat|detach|slip|broke|came loose)"),
    ("loss of drive or control in motion",
     r"snowmobile|\be[ -]?bike\b|electric bicycle|electric scooter|utility vehicle",
     r"clutch (?:fail|shatter)|sudden(?:ly)? (?:loss of power|shut)|shuts? off suddenly|brak(?:e|es) (?:failed|locked)"),
    ("safety interlock fails",
     r"blade|saw|mower|shredder",
     r"safety bar|brake|chain break|hand break|interlock",
     r"continued to (?:turn|spin|run)|chain spun|failed to stop|kept (?:running|spinning)|would not stop"),
)

_COMPILED = [(name, re.compile(context), [re.compile(term) for term in evidence])
             for name, context, *evidence in FAMILIES]


def signals(row: dict) -> set[str]:
    story = " ".join((row.get("incident_description") or "").lower().split())
    context = " ".join((row.get("product_type") or "", row.get("product_description") or "", story)).lower()
    return {name for name, context_re, evidence in _COMPILED
            if context_re.search(context) and all(term.search(story) for term in evidence)}
