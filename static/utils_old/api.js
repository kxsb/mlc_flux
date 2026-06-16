export async function apiGet(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`GET ${url} failed: ${response.status} ${text}`);
  }
  return response.json();
}

export async function apiPost(url, body = null) {
  const options = {
    method: "POST",
    headers: {}
  };

  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`POST ${url} failed: ${response.status} ${text}`);
  }
  return response.json();
}