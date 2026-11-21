"""Match the same independent set of reports to CPSC actions, regardless of watchlist flags.

Strict requires a listed model (including a distinctive marketed model name). Loose
requires independent evidence for the maker/brand, product type and reported hazard.
The two tiers can overlap. Dates are relative to publication. An earlier/equal-day
covered model blocks credit for later notices; a mere earlier category match does
not establish that the unit was recalled. Human decisions can correct either tier
or establish an earlier covered product whose notice did not list its model.
"""
import csv
import html
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import NamedTuple

from cpsc360.derive import manufacturer_key, match_text, product_model_key, tag_hazards


def clean(value):
    return " ".join(re.findall(r"[a-z0-9]+", html.unescape(str(value or "")).lower()))


def day(value):
    return date.fromisoformat(str(value)[:10])


def names(notice, group, fields=("Name",)):
    return " ".join(str(item.get(key) or "") for item in notice.get(group, []) for key in fields)


# Product, corporate and geographical words by themselves do not identify a maker.
ORG_STOP = set("""a an the of by for and inc corp corporation incorporated company co group
holding holdings products product consumer industries industry industrial manufacturing manufacturer
manufacturers international america american north canada usa electronics electronic electric
global division llc ltd limited llp plc na us uk unknown none not available china hong kong
technology technologies online retail retailer brands brand sales distribution imports trading
baby home kitchen outdoor furniture safety sports sport appliances appliance toy toys tools
parts solutions services systems supply design designs innovations enterprises goods
shenzhen ningbo guangdong dongguan guangzhou zhejiang jiangsu shanghai hangzhou beijing
ltd black white red silver blue green one world new best general first smart stack store
stores amazon ebay walmart target other brandname model household energy power bicycle""".split())
TYPE_STOP = ORG_STOP | set("""or in including unspecified powered manual gas general use
with related accessories accessory equipment electric electrical portable other all set kit
piece item items recalled childrens children adult residential commercial indoor units personal
type combination combo large small unclassified unpowered riding wheel wheels multi cordless
motor motorized miscellaneous attached intended years model models without for light appliance specified entire nylon steel
stainless plastic metal wooden wood frame black white red silver blue green model sold
trademark color edition digital lithium ion volt""".split())
MODEL_STOP = TYPE_STOP | set("""ice pro plus max series air mini original new classic premium
standard professional stainless steel deluxe black white blue red gold gray grey pink size
double single inch inches inchs unknown n a year this same various one two twin full king
queen range oven microwave ovens dishwasher refrigerator washer dryer stove toy chair bike
pool heater battery charger fan blender pan pot treadmill toaster mattress unspecified
pressure cooker recall basic see photo photo attached pictures number serial above countertop
freezer fridge kenmore product fridge stove model builtin gas smart front load top glass
grill desk tire bottle shelves scooter iron washing machine side door maker""".split())

# Equalize different CPSC and consumer vocabulary for the same product type.
TYPE_GROUPS = {
    "range": r"\b(?:ranges?|stoves?|cooktops?)\b",
    "refrigerator": r"\b(?:refrigerators?|fridges?)\b",
    "washer": r"\b(?:washing machines?|clothes washers?)\b",
    "bike": r"\b(?:bicycl\w*|bikes?|e bikes?)\b",
    "dumbbell": r"\b(?:dumbbells?|dumb bells?|adjustable weights?)\b",
    "dresser": r"\b(?:dressers?|chests? of drawers?|clothing storage units?)\b",
    "powerbank": r"\b(?:power banks?|powerbanks?|portable chargers?)\b",
    "pressurecooker": r"\b(?:pressure cookers?|multi cookers?|multicookers?)\b",
    "hoverboard": r"\b(?:hoverboards?|self balancing scooters?)\b",
    "mower": r"\b(?:lawn ?mowers?|lawn tractors?)\b",
    "beds": r"\b(?:beds?|bedframes?)\b",
}


def types(text):
    words = set(clean(text).split()) - TYPE_STOP
    stems = {w[:-3] + "y" if w.endswith("ies") else w.rstrip("s") for w in words if len(w) >= 3 and w.isalpha()}
    return stems | {k for k, p in TYPE_GROUPS.items() if re.search(p, text, re.I)}


def hazard_set(text):
    found = set(tag_hazards(text))
    if re.search(r"\b(?:separat\w*|break(?:age|s)?|broken|broke|fractur\w*|fail(?:ed|ure)? (?:at|under) the|eject\w*)\b", text, re.I):
        found.add("structural")
    if re.search(r"\b(?:impal\w*|punctur\w*|cut(?:ting|s)? (?:hazard|injur\w*)|cutting (?:his|her|my))\b", text, re.I):
        found.add("laceration")
    if re.search(r"\b(?:CO|carbon monoxide)\b", text):
        found.add("chemical")
    return found


def aliases(maker, brand):
    result = set()
    for raw in (maker, brand):
        if not raw:
            continue
        parts = [manufacturer_key(raw), *re.findall(r"\(([^()]+)\)", raw)]
        for part in parts:
            words = clean(part).split()
            distinctive = [w for w in words if w not in ORG_STOP and len(w) >= 2]
            if distinctive:
                result.update((" ".join(words), " ".join(distinctive)))
                # The first word is commonly the distinctive label in a longer legal name.
                if len(distinctive[0]) >= 3:
                    result.add(distinctive[0])
    return {r for r in result if r and r not in ORG_STOP}


ID_RE = re.compile(r"\b[a-z0-9]+(?:[._/-][a-z0-9]+)*\b", re.I)


# Ratings, dimensions, ordinals and counts look like model codes in product copy.
SPEC = re.compile(r"(?:[0-9.]+(?:inch(?:es)?|ft|foot|feet|mm|cm|kg|lb|oz|ml|gal|gallon|qt|quart|cup|pint|piece|pc|pack|speed|point|year|drawer|step|slice|wick|volt|amp|watt|btu|mah|ah|wh|hp|rpm|hz|mph|cc|k|v|w|st|nd|rd|th)s?|\d+in\d+|\d+x\d+)")


def identifiers(text):
    return {
        match_text(token) for token in ID_RE.findall(text)
        if len(token) >= 4 and re.search(r"[a-z]", token, re.I)
        and re.search(r"\d", token) and not SPEC.fullmatch(match_text(token))
    }


def model_terms(report):
    model = report.get("model") or ""
    maker = report.get("manufacturer_name") or ""
    brand = report.get("brand") or ""
    text = " ".join((report.get("product_description") or "", report.get("incident_description") or ""))
    codes = identifiers(text)
    key = product_model_key(model, brand, maker)
    numeric, named = set(), set()
    if key:
        codes.update(identifiers(model))
        core = re.sub(r"^(?:model(?: number| no)?\s*[:#.-]?\s+)", "", model.strip(), flags=re.I)
        if re.search(r"[a-z]", core, re.I) and re.search(r"\d", core) and len(core.split()) <= 4:
            codes.add(match_text(core))
        if re.fullmatch(r"[\d .-]+", core) and len(match_text(core)) >= 2:
            numeric.add(match_text(core))
        if not re.search(r"\d", core) and 1 <= len(core.split()) <= 8:
            words = set(clean(core).split()) - set(clean(maker + " " + brand).split())
            if words - MODEL_STOP:
                named.add(clean(core))
    return codes, numeric, named


@dataclass
class Links:
    strict: dict[str, int] = field(default_factory=dict)
    loose: dict[str, int] = field(default_factory=dict)
    prior: set[str] = field(default_factory=set)


def read_overrides(path):
    if path is None:
        return {}
    out = {}
    with Path(path).open() as f:
        for row in csv.DictReader(f):
            pair = row["report_no"], row["notice_no"]
            value = row["verdict"]
            if pair in out or value not in {"both", "strict", "loose", "none", "prior"}:
                raise ValueError(f"Invalid or duplicate review: {row}")
            out[pair] = value
    return out


class NoticeTerms(NamedTuple):
    date: date
    identity: str
    codes: set[str]
    organizations: str
    types: set[str]
    hazards: set[str]


def notice_terms(n):
    title = n.get("Title") or ""
    description = n.get("Description") or ""
    products = names(n, "Products", ("Name", "Description", "Model", "Type"))
    caption = names(n, "Images", ("Caption",))
    identity = clean(" ".join((title, products, description, caption)))
    # Description and captions can be the only locations listing the model.
    codes = identifiers(" ".join((title, products, description, caption)))
    org = " ".join(names(n, k) for k in ("Manufacturers", "Distributors", "Importers"))
    org = clean(org + " " + title + " " + products + " " + description)
    hazard = names(n, "Hazards")
    return NoticeTerms(
        day(n["RecallDate"]), identity, codes, org,
        types(products or title.split(" Due ")[0]), hazard_set(hazard + " " + title),
    )


def link_reports(reports, notices, overrides=None, candidates=None, horizon=365):
    """Link reports to notices announced at most `horizon` days after publication."""
    overrides = overrides or {}
    ledger, by_org_word, by_model = {}, defaultdict(set), defaultdict(set)
    for n in notices:
        no = str(n["RecallNumber"])
        prepared = notice_terms(n)
        ledger[no] = prepared
        for word in set(prepared.organizations.split()) - ORG_STOP:
            by_org_word[word].add(no)
        for code in prepared.codes:
            by_model[code].add(no)
    reviewed = defaultdict(set)
    for rid, no in overrides:
        if no not in ledger:
            raise ValueError(f"Unknown notice {no}")
        reviewed[rid].add(no)

    type_words = set().union(*(types(r.get("product_type") or "") for r in reports))
    labels = {}
    for report in reports:
        rid = report["report_no"]
        pub = day(report["publication_date"])
        maker = aliases(report.get("manufacturer_name"), report.get("brand"))
        codes, numeric, named = model_terms(report)
        ptype = types(report.get("product_type") or report.get("product_subcategory") or "")
        maker_words = types((report.get("manufacturer_name") or "") + " " + (report.get("brand") or ""))
        product = types(report.get("product_description") or "") & (type_words - maker_words)
        hazard = hazard_set(report.get("incident_description") or "")
        possible = set(reviewed[rid])
        for alias in maker:
            possible.update(by_org_word[alias.split()[0]])
        for code in codes:
            possible.update(by_model[code])

        links = Links()
        labels[rid] = links
        for no in sorted(possible):
            notice = ledger[no]
            lead = (notice.date - pub).days
            if lead > horizon:
                continue
            org_match = any(f" {name} " in f" {notice.organizations} " for name in maker)
            code_match = codes & notice.codes
            product_match = (ptype | product) & notice.types
            hazard_match = hazard & notice.hazards
            model_match = set(code_match)
            if org_match:
                model_match.update(s for s in numeric | named if f" {s} " in f" {notice.identity} ")
                # Recover model codes split in the notice by a space instead of a dash.
                for c in codes - notice.codes:
                    if len(c) >= 5 and re.search(r"\b" + r"\s*".join(c) + r"\b", notice.identity):
                        model_match.add(c)
            strict = bool(model_match and (org_match or product_match))
            loose = bool(org_match and product_match and hazard_match)
            value = overrides.get((rid, no))
            if value:
                strict = value in {"strict", "both"}
                loose = value in {"loose", "both"}
            prior = lead <= 0 and (strict or value == "prior")
            if candidates is not None and (strict or loose or value or model_match or (org_match and ptype & notice.types)):
                candidates.append(dict(report_no=rid, notice_no=no, lead=lead, strict=strict, loose=loose, reason=" ".join([
                    "org" if org_match else "", ",".join(sorted(model_match)),
                    ",".join(sorted(product_match)), ",".join(sorted(hazard_match)),
                ]).strip()))
            if prior:
                links.prior.add(no)
            if lead > 0:
                if strict:
                    links.strict[no] = lead
                if loose:
                    links.loose[no] = lead
        if links.prior:
            links.strict.clear()
            links.loose.clear()
    return labels
