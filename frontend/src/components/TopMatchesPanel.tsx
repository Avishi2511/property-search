import type { TopMatch } from "../types";
import { formatPrice } from "../format";

interface Props {
  matches: TopMatch[];
}

export function TopMatchesPanel({ matches }: Props) {
  if (matches.length === 0) return null;

  return (
    <section className="panel matches-panel">
      <header className="panel-header">
        <h2>Top matches</h2>
      </header>
      <div className="match-list">
        {matches.map((m) => (
          <div key={m.id} className="match-card">
            <div className="match-card-top">
              <span className="match-project">{m.project}</span>
              <span className="match-score">{Math.round(m.score)}</span>
            </div>
            <div className="match-meta">
              {m.location} · {m.bedrooms} BHK · {formatPrice(m.price)} · possession {m.possession}
            </div>
            <div className="match-builder">{m.builder}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
