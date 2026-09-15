import type { Profile } from "../types";
import { fieldLabel, formatConstraintValue } from "../format";

interface Props {
  profile: Profile | null;
}

const TYPE_COLORS: Record<string, string> = {
  hard: "#c2410c",
  soft: "#2563eb",
  preference: "#7c3aed",
  context: "#0f766e",
};

export function BuyerProfilePanel({ profile }: Props) {
  const entries = profile ? Object.entries(profile.constraints) : [];

  return (
    <section className="panel profile-panel">
      <header className="panel-header">
        <h2>Buyer requirements</h2>
      </header>

      {entries.length === 0 && <p className="empty-hint">Nothing known yet — start the conversation.</p>}

      <div className="requirement-chips">
        {entries.map(([field, c]) => (
          <div key={field} className="requirement-chip">
            <div className="requirement-chip-top">
              <span className="requirement-dot" style={{ background: TYPE_COLORS[c.type] }} />
              <span className="requirement-label">{fieldLabel(field)}</span>
            </div>
            <div className="requirement-value">{formatConstraintValue(field, c)}</div>
            {c.changed && c.previous !== null && c.previous !== undefined && (
              <div className="requirement-previous">was {formatPrevious(field, c.previous)}</div>
            )}
            <div className="requirement-confidence">
              <div className="requirement-confidence-fill" style={{ width: `${Math.round(c.confidence * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>

      {profile && profile.unknowns.length > 0 && (
        <div className="unknowns">
          <h3>Still unknown</h3>
          <div className="unknown-chips">
            {profile.unknowns.map((f) => (
              <span key={f} className="unknown-chip">
                {fieldLabel(f)}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function formatPrevious(field: string, previous: unknown): string {
  if (field === "budget") {
    if (typeof previous === "number") return `₹${(previous / 10_000_000).toFixed(2)} Cr`;
    if (previous && typeof previous === "object" && "min" in (previous as any)) {
      const p = previous as { min: number | null; max: number | null };
      if (p.min != null && p.max != null) {
        return `₹${(p.min / 10_000_000).toFixed(2)}–${(p.max / 10_000_000).toFixed(2)} Cr`;
      }
    }
  }
  if (typeof previous === "boolean") return previous ? "Yes" : "No";
  return String(previous);
}
