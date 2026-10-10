import { useState } from "react";
import { optimizeRoute } from "./api";

const MAX_DELIVERIES = 10;

function emptyDelivery() {
  return { name: "", latitude: "", longitude: "", priority: "MEDIUM" };
}

function IndexPage({ onResult }) {
  // Sample values so the form can be tested quickly. Change them freely.
  const [warehouse, setWarehouse] = useState({
    name: "Main Warehouse",
    latitude: "13.0827",
    longitude: "80.2707",
  });
    const [countText, setCountText] = useState("1");
  const [deliveries, setDeliveries] = useState([
    { name: "T Nagar Store", latitude: "13.0418", longitude: "80.2341", priority: "HIGH" },
  ]);
  const [mode, setMode] = useState("with");
  const [problems, setProblems] = useState([]);
  const [loading, setLoading] = useState(false);

  function changeWarehouse(field, value) {
    setWarehouse({ ...warehouse, [field]: value });
  }

  // When the number of deliveries changes, add or remove rows.
  function changeCount(text) {
    setCountText(text);
    const count = parseInt(text);
    if (isNaN(count) || count < 1 || count > MAX_DELIVERIES) {
      return;
    }
    const rows = deliveries.slice(0, count);
    while (rows.length < count) {
      rows.push(emptyDelivery());
    }
    setDeliveries(rows);
  }

  function changeDelivery(index, field, value) {
    const rows = deliveries.slice();
    rows[index] = { ...rows[index], [field]: value };
    setDeliveries(rows);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setProblems([]);

    const count = parseInt(countText);
    if (isNaN(count) || count < 1 || count > MAX_DELIVERIES) {
      setProblems(["Number of deliveries must be between 1 and " + MAX_DELIVERIES]);
      return;
    }

    setLoading(true);
    try {
      // The backend checks every value and sends clear messages if something is wrong.
      const result = await optimizeRoute({
        warehouse: warehouse,
        deliveries: deliveries,
        use_priority: mode === "with",
      });
      onResult(result);
    } catch (error) {
      setProblems(error.problems || ["Something went wrong"]);
    }
    setLoading(false);
  }

  return (
    <div>
      <h1>Delivery Route Optimizer</h1>

      <form onSubmit={handleSubmit}>
        <h2>Warehouse</h2>
        <label>Name </label>
        <input value={warehouse.name} onChange={(e) => changeWarehouse("name", e.target.value)} />
        <br />
        <label>Latitude </label>
        <input value={warehouse.latitude} onChange={(e) => changeWarehouse("latitude", e.target.value)} />
        <br />
        <label>Longitude </label>
        <input value={warehouse.longitude} onChange={(e) => changeWarehouse("longitude", e.target.value)} />

        <h2>Deliveries</h2>
        <label>Number of deliveries (1 to {MAX_DELIVERIES}) </label>
        <input type="number" value={countText} onChange={(e) => changeCount(e.target.value)} />

        {deliveries.map((delivery, index) => (
          <div className="delivery-box" key={index}>
            <strong>Delivery {index + 1}</strong>
            <br />
            <label>Name </label>
            <input value={delivery.name} onChange={(e) => changeDelivery(index, "name", e.target.value)} />
            <br />
            <label>Latitude </label>
            <input value={delivery.latitude} onChange={(e) => changeDelivery(index, "latitude", e.target.value)} />
            <br />
            <label>Longitude </label>
            <input value={delivery.longitude} onChange={(e) => changeDelivery(index, "longitude", e.target.value)} />
            <br />
            <label>Priority </label>
            <select value={delivery.priority} onChange={(e) => changeDelivery(index, "priority", e.target.value)}>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </div>
        ))}

        <h2>Mode</h2>
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="with">With Priority</option>
          <option value="without">Without Priority</option>
        </select>

        {problems.length > 0 && (
          <div className="error-box">
            <strong>Please fix these problems:</strong>
            <ul>
              {problems.map((problem, index) => (
                <li key={index}>{problem}</li>
              ))}
            </ul>
          </div>
        )}

        <br />
        <button type="submit" disabled={loading}>
          {loading ? "Working..." : "Submit"}
        </button>
      </form>
    </div>
  );
}

export default IndexPage;
