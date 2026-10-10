import { useState } from "react";
import IndexPage from "./IndexPage";
import ResultPage from "./ResultPage";

function App() {
  // result stays null until the backend sends an answer.
  const [result, setResult] = useState(null);

  // The index page is hidden (not removed) while the result is shown,
  // so the form keeps what the user typed when they press OK.
  return (
    <div className="page">
      <div style={{ display: result === null ? "block" : "none" }}>
        <IndexPage onResult={setResult} />
      </div>

      {result !== null && (
        <ResultPage result={result} onOk={() => setResult(null)} />
      )}
    </div>
  );
}

export default App;
