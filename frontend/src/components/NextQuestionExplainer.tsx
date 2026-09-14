import type { DiscoveryDecision } from "../types";
import { fieldLabel } from "../format";

interface Props {
  discovery: DiscoveryDecision | null;
}

export function NextQuestionExplainer({ discovery }: Props) {
  if (!discovery) return null;

  return (
    <section className="panel explainer-panel">
      <header className="panel-header">
        <h2>{discovery.should_stop ? "Discovery complete" : "Next question"}</h2>
      </header>

      {discovery.should_stop ? (
        <p className="explainer-stop-reason">{discovery.stop_reason}</p>
      ) : (
        discovery.next_question && (
          <div className="explainer-body">
            <div className="explainer-field">{fieldLabel(discovery.next_question.field)}</div>
            <div className="explainer-reduction">
              <span className="explainer-reduction-value">{discovery.next_question.estimated_reduction_pct}%</span>
              <span className="explainer-reduction-label">expected search reduction</span>
            </div>
            <p className="explainer-reason">{discovery.next_question.reason}</p>
          </div>
        )
      )}
    </section>
  );
}
