// Schematic diagram: the stops are placed on a circle in visiting order.
// It is NOT a map, positions do not use real coordinates.
function RouteDiagram({ result }) {
  // The route ends at the warehouse again, so leave out the last stop here.
  const stops = result.route.slice(0, result.route.length - 1);
  const count = stops.length;
  const centerX = 200;
  const centerY = 200;
  const radius = 140;

  // With only 2 stops, the going and returning lines need more space between them.
  const bend = count === 2 ? 80 : 30;

  const points = [];
  for (let i = 0; i < count; i++) {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / count;
    points.push({
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    });
  }

  // One curved line for every leg, including the return to the warehouse.
  const lines = [];
  for (let i = 0; i < result.legs.length; i++) {
    const from = points[i];
    const to = points[(i + 1) % count];
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.sqrt(dx * dx + dy * dy);
    // Push the curve to the side so two legs between the same stops do not overlap.
    const sideX = (-dy / length) * bend;
    const sideY = (dx / length) * bend;

    lines.push(
      <g key={i}>
        <path
          d={"M " + from.x + " " + from.y + " Q " + (midX + sideX) + " " + (midY + sideY) + " " + to.x + " " + to.y}
          fill="none"
          stroke="#555"
          strokeWidth="1.5"
        />
        <text x={midX + sideX / 2} y={midY + sideY / 2} fontSize="11" textAnchor="middle" fill="#b00">
          {result.legs[i].distance_km} km
        </text>
      </g>
    );
  }

  const nodes = [];
  for (let i = 0; i < count; i++) {
    nodes.push(
      <g key={i}>
        <circle cx={points[i].x} cy={points[i].y} r="16" fill={i === 0 ? "#228844" : "#3366cc"} />
        <text x={points[i].x} y={points[i].y + 4} fontSize="12" textAnchor="middle" fill="white">
          {i === 0 ? "W" : i}
        </text>
        <text x={points[i].x} y={points[i].y - 22} fontSize="10" textAnchor="middle">
          {stops[i].name}
        </text>
      </g>
    );
  }

  return (
    <svg viewBox="0 0 400 400" width="100%" style={{ maxWidth: "500px" }}>
      {lines}
      {nodes}
    </svg>
  );
}

function ResultPage({ result, onOk }) {
  return (
    <div>
      <h1>Optimized Route</h1>

      <p>
        <strong>Priority:</strong> {result.use_priority ? "With Priority" : "Without Priority"}
      </p>
      <p>
        <strong>Total distance:</strong> {result.total_distance_km} km
      </p>

      {result.saved ? (
        <p>Saved in the database (id {result.route_id}).</p>
      ) : (
        <p className="error-box">{result.save_error}</p>
      )}

      <h2>Visiting order</h2>
      <ol start="0">
        {result.route.map((stop, index) => (
          <li key={index}>
            {index === 0 && "Start at warehouse: "}
            {index === result.route.length - 1 && "Return to warehouse: "}
            {stop.name}
            {stop.priority ? " (" + stop.priority + ")" : ""} - {stop.km_from_start} km from start
          </li>
        ))}
      </ol>

      <h2>Diagram</h2>
      <RouteDiagram result={result} />
      <p>The diagram is schematic. Numbers show the visiting order (W = warehouse).</p>

      <h2>Distance of each leg</h2>
      <table>
        <thead>
          <tr>
            <th>From</th>
            <th>To</th>
            <th>Distance (km)</th>
          </tr>
        </thead>
        <tbody>
          {result.legs.map((leg, index) => (
            <tr key={index}>
              <td>{leg.from}</td>
              <td>{leg.to}</td>
              <td>{leg.distance_km}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p>
        <em>{result.note}</em>
      </p>

      <button onClick={onOk}>OK</button>
    </div>
  );
}

export default ResultPage;
