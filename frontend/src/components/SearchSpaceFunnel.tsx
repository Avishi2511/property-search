import type { SearchSpace } from "../types";

interface Props {
  searchSpace: SearchSpace | null;
}

export function SearchSpaceFunnel({ searchSpace }: Props) {
  if (!searchSpace || searchSpace.history.length === 0) return null;

  const max = searchSpace.history[0] || 1;

  return (
    <section className="panel funnel-panel">
      <header className="panel-header">
        <h2>Search space</h2>
      </header>
      <div className="funnel">
        {searchSpace.history.map((count, i) => {
          const widthPct = Math.max(6, Math.round((count / max) * 100));
          const isLast = i === searchSpace.history.length - 1;
          return (
            <div key={i} className="funnel-row">
              <div
                className={`funnel-bar ${isLast ? "funnel-bar-final" : ""}`}
                style={{ width: `${widthPct}%` }}
              >
                {count}
              </div>
              {i < searchSpace.history.length - 1 && <span className="funnel-arrow">↓</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
