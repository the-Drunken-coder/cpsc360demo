import type { HazardKey } from "../api/types";

export const HAZARD_LABELS: Record<HazardKey, string> = {
  fire: "Fire",
  overheating: "Overheating / melting",
  burn: "Burn / scald",
  shatter_explosion: "Shattering / explosion",
  fall: "Fall",
  electrical: "Electrical shock / arcing",
  structural: "Structural / mechanical failure",
  chemical: "Chemical / toxic exposure",
  laceration: "Laceration / cut",
  choking: "Choking / ingestion",
  entrapment: "Entrapment / pinching / crushing",
  battery: "Battery failure",
  suffocation: "Suffocation / strangulation",
  tip_over: "Tip-over",
  drowning: "Drowning / submersion",
};

export function isHazardKey(value: string): value is HazardKey {
  return value in HAZARD_LABELS;
}
