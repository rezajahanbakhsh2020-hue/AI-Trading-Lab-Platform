import { HostSnapshot } from "../../architecture/hostView";

type StrategyCardProps = {
  snapshot: HostSnapshot;
};

export function StrategyCard({ snapshot }: StrategyCardProps) {
  const strategy = snapshot.strategy;

  return (
    <div className="card">
      <div className="card-head">
        <div>
          <h3>Strategy Presentation</h3>
          <p className="hint">Strategy logic, decision models, and stability owned by Project 1.</p>
        </div>
        <span className="status unavailable">Project 1 Owned</span>
      </div>

      <div className="card-body">
        <table className="table">
          <tbody>
            <tr>
              <th>Strategy Identity</th>
              <td>{strategy.name ?? "Unavailable"}</td>
            </tr>
            <tr>
              <th>Stability Score</th>
              <td>
                {strategy.stability != null
                  ? `${strategy.stability}/100`
                  : "Unavailable"}
              </td>
            </tr>
            <tr>
              <th>Validation Boundary</th>
              <td>Project1IntegrationPort Contract</td>
            </tr>
          </tbody>
        </table>
        <p className="hint" style={{ marginTop: 12 }}>
          {strategy.message}
        </p>
      </div>
    </div>
  );
}
