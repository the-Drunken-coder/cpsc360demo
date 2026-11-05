from datetime import date
from pathlib import Path

from cpsc360.derive import manufacturer_key, model_key, product_model_key, tag_hazards
from cpsc360.source_csv import parse_export

FIXTURES = Path(__file__).parent / "fixtures"


def test_bulk_file_decodes_windows_1252_without_replacement_characters():
    rows = list(parse_export((FIXTURES / "bulk_sample.csv").read_bytes()))
    assert len(rows) == 2
    narratives = [row.typed["incident_description"] for row in rows]
    assert any("’" in text for text in narratives)
    assert all("�" not in text for text in narratives)


def test_bulk_row_types_and_verbatim_raw():
    rows = {row.report_no: row for row in parse_export((FIXTURES / "bulk_sample.csv").read_bytes())}
    row = rows["20261012-61869-2147307978"]
    assert row.typed["report_date"] == date(2026, 10, 12)
    assert row.typed["publication_date"] == date(2026, 11, 4)
    assert row.typed["product_type"] == "Squeeze or Squeaker Toys"
    assert row.typed["product_code"] == "1350"
    assert row.typed["upc"] == "887258013033"
    assert row.raw["UPC"] == "'887258013033"
    assert row.typed["victim_age"] == 7


def test_export_severity_matches_bulk_vocabulary():
    rows = list(parse_export((FIXTURES / "export_sample.csv").read_bytes()))
    assert rows and all(row.typed["severity"].startswith("Injury, ") for row in rows)
    assert all(row.raw["(Primary) Victim Severity"].startswith("Injury - ") for row in rows)


def test_row_hash_is_stable():
    data = (FIXTURES / "bulk_sample.csv").read_bytes()
    assert [r.row_sha256 for r in parse_export(data)] == [r.row_sha256 for r in parse_export(data)]


def test_manufacturer_spellings_share_a_key():
    assert manufacturer_key("SAMSUNG ELECTRONICS AMERICA, INC. (SEA)") == manufacturer_key("Samsung Electronics")
    assert manufacturer_key("WHIRLPOOL CORPORATION") == "whirlpool"


def test_placeholder_models_never_match():
    assert model_key("I don't know") is None
    assert model_key("N/A") is None
    assert model_key("WRF-555 SDFZ") == "wrf555sdfz"
    assert model_key("GT") == "gt"
    assert model_key("See photos") is None
    assert model_key("None found") is None
    assert model_key("IMEI [REDACTED]") is None
    assert model_key("Polaris RZR 800 [REDACTED]") == "polarisrzr800redacted"
    assert model_key("HP OmniStudio All-in-One X27") == "hpomnistudioallinonex27"
    assert model_key("AW-R-NA-BLUE") == "awrnablue"
    assert model_key("Pelotón Tread +") == model_key("Peloton Tread+")


def test_a_model_that_repeats_the_brand_or_maker_names_no_product():
    assert product_model_key("Kenmore", "Kenmore", "Sears Holdings Management Corporation") is None
    assert product_model_key("Samsung", "Samsung", "SAMSUNG ELECTRONICS AMERICA, INC.") is None
    assert product_model_key("WRF555", "Whirlpool", "WHIRLPOOL CORPORATION") == "wrf555"


def test_hazard_tags_keep_the_matched_phrases():
    tags = tag_hazards("The oven door glass shattered and my hand was burned.")
    assert tags["shatter_explosion"] == ["shattered"]
    assert tags["burn"] == ["burned"]
    assert "fire" not in tags


def test_rash_reports_are_tagged_as_skin_irritation():
    tags = tag_hazards("Week old daughter has severe rashes and redness all where the diapers touching.")
    assert tags["skin_irritation"] == ["rashes", "redness"]
