import type { ReactNode } from "react";
import type { ReportedIncident } from "../../api/types";
import { ReportLink } from "../../components/text";
import { Section } from "./parts";

type Field = { key: keyof ReportedIncident; label: string };

const GROUPS: { title: string; fields: Field[] }[] = [
  {
    title: "Report",
    fields: [
      { key: "report_no", label: "Report No." },
      { key: "report_date", label: "Report date (submitted)" },
      { key: "publication_date", label: "Publication date" },
      { key: "sent_to_manufacturer_date", label: "Sent to manufacturer" },
      { key: "submitter_category", label: "Submitter" },
      { key: "severity", label: "Severity" },
      { key: "associated_report_nos", label: "Associated reports" },
    ],
  },
  {
    title: "Product",
    fields: [
      { key: "product_description", label: "Description" },
      { key: "product_category", label: "Category" },
      { key: "product_subcategory", label: "Subcategory" },
      { key: "product_type", label: "Product type" },
      { key: "product_code", label: "Product code" },
      { key: "manufacturer_name", label: "Manufacturer" },
      { key: "brand", label: "Brand" },
      { key: "model", label: "Model" },
      { key: "serial_number", label: "Serial number" },
      { key: "upc", label: "UPC" },
      { key: "date_manufactured", label: "Date manufactured" },
      { key: "manufacturer_date_code", label: "Manufacturer date code" },
    ],
  },
  {
    title: "Purchase",
    fields: [
      { key: "retailer", label: "Retailer" },
      { key: "retailer_state", label: "Retailer state" },
      { key: "purchase_date", label: "Purchase date" },
      { key: "purchase_date_is_estimate", label: "Purchase date is estimate" },
    ],
  },
  {
    title: "Location and victim",
    fields: [
      { key: "location", label: "Location" },
      { key: "city", label: "City" },
      { key: "state", label: "State" },
      { key: "zip", label: "ZIP" },
      { key: "victim_sex", label: "Victim sex" },
      { key: "victim_age", label: "Victim age" },
      { key: "relation_to_victim", label: "Submitter relation to victim" },
    ],
  },
  {
    title: "Submitter answers",
    fields: [
      { key: "submitter_has_product", label: "Still has product" },
      { key: "damaged_before_incident", label: "Damaged before incident" },
      { key: "damage_description", label: "Damage description" },
      { key: "damage_repaired", label: "Damage repaired" },
      { key: "modified_before_incident", label: "Modified before incident" },
      { key: "contacted_manufacturer", label: "Contacted manufacturer" },
      { key: "plans_to_contact", label: "Plans to contact manufacturer" },
      { key: "answer_explanation", label: "Explanation" },
    ],
  },
];

function display(key: keyof ReportedIncident, value: ReportedIncident[keyof ReportedIncident]): ReactNode {
  if (value === null || value === "") return <span className="empty-value">not reported</span>;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="empty-value">none</span>;
    return <span className="link-list">{value.map((r) => <ReportLink key={r} reportNo={r} />)}</span>;
  }
  if (key === "report_no" || key === "model" || key === "serial_number" || key === "upc") return <span className="mono">{value}</span>;
  return String(value);
}

export function ReportedFields({ reported }: { reported: ReportedIncident }) {
  return (
    <Section title="Reported fields" tier="reported">
      <div className="field-groups">
        {GROUPS.map((g) => (
          <div key={g.title} className="field-group">
            <h4>{g.title}</h4>
            <dl className="kv">
              {g.fields.map((f) => (
                <div key={f.key} className="kv-row">
                  <dt>{f.label}</dt>
                  <dd>{display(f.key, reported[f.key])}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </Section>
  );
}
