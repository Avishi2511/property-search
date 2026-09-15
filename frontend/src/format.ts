import type { ConstraintValue } from "./types";

export function formatPrice(amount: number): string {
  if (amount >= 10_000_000) return `₹${(amount / 10_000_000).toFixed(2)} Cr`;
  return `₹${(amount / 100_000).toFixed(1)} L`;
}

const FIELD_LABELS: Record<string, string> = {
  city: "City",
  bedrooms: "Bedrooms",
  budget: "Budget",
  locality: "Locality",
  possession_date: "Possession",
  purpose: "Purpose",
  parents_living_with_buyer: "Parents",
  office_location: "Office location",
  hospital_access: "Hospital access",
  buyer_commute: "Commute priority",
  floor_preference: "Floor preference",
  parking: "Parking",
  builder_preference: "Builder preference",
  amenities: "Amenities",
};

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field.replace(/_/g, " ");
}

// Deterministic "listing photo" gradient per property, since we have no real
// images — a stable hue derived from the id so the same property always
// looks the same, and neighboring properties still read as visually varied.
const GRADIENT_PAIRS: [string, string][] = [
  ["#1e3a5f", "#3b6ea5"],
  ["#134e4a", "#2f9e8f"],
  ["#4a2545", "#a55b9e"],
  ["#5c3d1e", "#c98a3f"],
  ["#1f3d2b", "#4e9b6a"],
  ["#3a2647", "#7a4fa8"],
  ["#4d1f2b", "#b8455f"],
  ["#1c3a4a", "#4a9ab8"],
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

export function thumbnailGradient(id: string): string {
  const [from, to] = GRADIENT_PAIRS[hashString(id) % GRADIENT_PAIRS.length];
  return `linear-gradient(135deg, ${from}, ${to})`;
}

export function formatConstraintValue(field: string, c: ConstraintValue): string {
  if (field === "budget") {
    if (c.min != null && c.max != null) {
      if (c.min === c.max) return formatPrice(c.min);
      return `${formatPrice(c.min)} – ${formatPrice(c.max)}`;
    }
    if (typeof c.value === "number") return formatPrice(c.value);
    return "—";
  }

  if (field === "bedrooms" && typeof c.value === "number") {
    return `${c.value} BHK`;
  }

  if (field === "possession_date" && typeof c.value === "string") {
    const [year, month] = c.value.split("-");
    const monthNames = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `Before ${monthNames[Number(month)]} ${year}`;
  }

  if (typeof c.value === "boolean") {
    return c.value ? "Yes" : "No";
  }

  if (c.value && typeof c.value === "object" && "near" in (c.value as any)) {
    const v = c.value as { near: string; max_minutes: number };
    return `Within ${v.max_minutes} min of ${v.near}`;
  }

  if (Array.isArray(c.value)) {
    return c.value.length ? c.value.join(", ") : "—";
  }

  if (typeof c.value === "string") {
    return c.value.charAt(0).toUpperCase() + c.value.slice(1);
  }

  return "—";
}
