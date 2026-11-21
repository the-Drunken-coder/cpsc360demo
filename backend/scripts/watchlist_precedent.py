"""Retrieve pre-2024 CPSC notices by product vocabulary and failure language."""

import re
from html import unescape

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer


# Normalize a few common differences between reports and agency language.
SYNONYMS = {
    "fell": "fall", "fallen": "fall", "falls": "fall", "falling": "fall",
    "broke": "break", "broken": "break", "breaks": "break", "breaking": "break",
    "burned": "burn", "burns": "burn", "burning": "burn", "burnt": "burn",
    "flames": "fire", "flame": "fire", "fires": "fire", "ignited": "ignite",
    "melted": "melt", "melting": "melt", "smoking": "smoke",
    "detached": "detach", "detaches": "detach", "detaching": "detach",
    "separated": "detach", "separates": "detach", "separate": "detach",
    "charging": "charge", "charged": "charge", "batteries": "battery",
    "choked": "choke", "choking": "choke", "swallowed": "swallow",
    "overheated": "overheat", "overheating": "overheat",
    "exploded": "explode", "explosion": "explode", "explodes": "explode",
}
STOP = ENGLISH_STOP_WORDS | set(
    "consumer consumers product products recall recalls recalled serious injury injuries "
    "posing poses hazard hazards risk sold used use using description other classified "
    "specified manufacturer model brand redacted report reports following item".split()
)


def words(value):
    return re.findall(r"\b[a-z]{3,}\b", unescape(value or "").lower())


def normalize_text(value, excluded):
    tokens = []
    for token in words(value):
        if token in STOP or token in excluded:
            continue
        word = SYNONYMS.get(token, token)
        if len(word) > 4 and word.endswith('s') and not word.endswith('ss'):
            word = word[:-1]
        tokens.append(word)
    return " ".join(tokens)


def grouped_names(notice, field):
    return " ".join(record.get("Name") or "" for record in notice.get(field, []))


def similarity(corpus, queries):
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform(corpus)
    return vectorizer.transform(queries) @ matrix.T


ORG_GENERIC = STOP | set("the corp corporation llc inc ltd limited brand company international american america industries group manufacturing electronics industrial technology distribution holding holdings appliance appliances tools supply products home amazon walmart target retail usa north global imports outdoor sports store trading consumer".split())


def org_terms(text):
    return {w for w in words(text) if w not in ORG_GENERIC and len(w) >= 3}


def precedent_strength(rows, notices):
    """Best joint score must come from the same historical notice on both axes."""
    if any(str(row["publication_date"])[:10] < "2024-01-01" for row in rows):
        raise ValueError("The precedent index is frozen for reports published in 2024 or later")
    products, hazards, maker_index = [], [], {}
    for n in notices:
        if n['RecallDate'][:10] >= '2024-01-01':
            continue
        excluded = set(words(" ".join(grouped_names(n, f) for f in (
            'Manufacturers', 'Distributors', 'Importers'
        ))))
        p = normalize_text(grouped_names(n, 'Products'), excluded)
        h = normalize_text(grouped_names(n, 'Hazards'), excluded)
        if p and h:
            for term in org_terms(" ".join(excluded)) | org_terms(grouped_names(n, "Products")):
                maker_index.setdefault(term, []).append(len(products))
            products.append(p)
            hazards.append(h)

    query_products, query_hazards = [], []
    makers_i, makers_j = [], []
    for i, row in enumerate(rows):
        maker_terms = org_terms(" ".join(row.get(f) or "" for f in ("manufacturer_name", "brand")))
        indices = {j for term in maker_terms for j in maker_index.get(term, ())}
        makers_i.extend([i] * len(indices))
        makers_j.extend(indices)
        excluded = set(words(" ".join(row.get(f) or "" for f in (
            "manufacturer_name", "brand", "model", "retailer"
        ))))
        product_type = row.get("product_type") or ""
        desc = row.get("product_description") or ""
        query_products.append(normalize_text(f"{product_type} {product_type} {desc}", excluded))
        query_hazards.append(normalize_text(row.get("incident_description"), excluded))

    if not rows or not products:
        return np.zeros(len(rows)), np.zeros(len(rows))
    product_sim = similarity(products, query_products)
    hazard_sim = similarity(hazards, query_hazards)
    joint = product_sim.multiply(hazard_sim)
    same_maker = csr_matrix((np.ones(len(makers_i)), (makers_i, makers_j)), shape=joint.shape)
    related = joint.multiply(same_maker)
    return tuple(np.sqrt(matrix.max(axis=1).toarray().ravel()) for matrix in (joint, related))


def precedent_signals(rows, notices):
    strength, related = precedent_strength(rows, notices)
    result = {}
    for row, score, same in zip(rows, strength, related):
        active = {f"precedent_{cut}" for cut in (25, 30, 35, 40, 45, 50) if score >= cut / 100}
        active.update(f"related_precedent_{cut}" for cut in (15, 20, 25, 30, 35, 40) if same >= cut / 100)
        result[row["report_no"]] = active
    return result
