const API = process.env.REACT_APP_API_URL || "http://localhost:8000";

export async function apiFetch(path, options = {}) {
  return fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
}
