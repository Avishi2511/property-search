import type { TopMatch } from "../types";
import { formatPrice, thumbnailGradient } from "../format";

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
          <article key={m.id} className="listing-card">
            <div className="listing-thumb" style={{ background: thumbnailGradient(m.id) }}>
              <svg viewBox="0 0 24 24" width="32" height="32" fill="none" className="listing-thumb-icon">
                <path
                  d="M3 11.5 12 4l9 7.5M5.5 10v9a1 1 0 0 0 1 1H10v-5.5h4V20h3.5a1 1 0 0 0 1-1v-9"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span className="listing-price-badge">{formatPrice(m.price)}</span>
              <span className="listing-score-badge">{Math.round(m.score)}% match</span>
            </div>
            <div className="listing-body">
              <div className="listing-title-row">
                <h3>{m.project}</h3>
              </div>
              <p className="listing-location">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none">
                  <path
                    d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12Z"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                  <circle cx="12" cy="10" r="2.4" stroke="currentColor" strokeWidth="1.6" />
                </svg>
                {m.location}
              </p>
              <div className="listing-facts">
                <span>{m.bedrooms} BHK</span>
                <span>·</span>
                <span>{m.area_sqft.toLocaleString()} sqft</span>
                <span>·</span>
                <span>possession {m.possession}</span>
              </div>
              <div className="listing-footer">
                <span className="listing-builder">{m.builder}</span>
                {m.amenities.slice(0, 3).map((a) => (
                  <span key={a} className="amenity-chip">
                    {a.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
