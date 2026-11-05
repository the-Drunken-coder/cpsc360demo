import type { HazardKey } from "../api/types";

export const HAZARD_LABELS: Record<HazardKey, string> = {
  fire: "Fire",
  overheating: "Overheating",
  electrical: "Electrical",
  burn: "Burn",
  shatter_explosion: "Shatter / explosion",
  laceration: "Laceration",
  choking: "Choking",
  suffocation: "Suffocation",
  entrapment: "Entrapment",
  fall: "Fall",
  tip_over: "Tip-over",
  chemical: "Chemical",
  structural: "Structural failure",
  battery: "Battery",
  drowning: "Drowning",
};

export function isHazardKey(value: string): value is HazardKey {
  return value in HAZARD_LABELS;
}
