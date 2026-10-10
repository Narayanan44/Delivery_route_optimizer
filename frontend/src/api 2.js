// Address of the backend. For deployment we set VITE_API_URL.
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function optimizeRoute(requestData) {
  let response;
  try {
    response = await fetch(API_URL + "/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestData),
    });
  } catch (error) {
    const problem = new Error("Cannot reach the server");
    problem.problems = ["Cannot reach the server. Is the backend running?"];
    throw problem;
  }

  let data = null;
  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const problem = new Error("Request failed");
    // The backend sends status 400 with a list of readable messages.
    if (response.status === 400 && data && Array.isArray(data.detail)) {
      problem.problems = data.detail;
    } else {
      problem.problems = ["The server could not process the request."];
    }
    throw problem;
  }

  return data;
}
