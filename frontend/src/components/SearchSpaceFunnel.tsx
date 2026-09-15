import type { SearchSpace } from "../types";

interface Props {
  searchSpace: SearchSpace | null;
}

export function SearchSpaceFunnel({ searchSpace }: Props) {
  if (!searchSpace || searchSpace.history.length === 0) return null;

  return (
    <section className="panel funnel-panel">
      <header className="panel-header">
        <h2>Search space</h2>
      </header>
      <div className="funnel-track">
        {searchSpace.history.map((count, i) => {
          const isLast = i === searchSpace.history.length - 1;
          return (
            <div className="funnel-step" key={i}>
              <span className={`funnel-chip ${isLast ? "funnel-chip-final" : ""}`}>{count}</span>
              {i < searchSpace.history.length - 1 && <span className="funnel-track-arrow">→</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
