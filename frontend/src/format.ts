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
