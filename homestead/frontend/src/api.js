// Calls to the Homestead server. URLs are relative to the page, so they work
// both behind Home Assistant's ingress and on a stand-alone server.

const base = new URL(".", window.location.href);

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function api(path, { method = "GET", body, params } = {}) {
  const url = new URL(`api/${path}`, base);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  }
  const response = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let message = response.statusText;
    try {
      const detail = (await response.json()).detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.map((item) => item.msg).join(", ");
    } catch {
      // Not JSON: keep the status text.
    }
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? null : response.json();
}

// Calls `onNotice` whenever the server says data changed; reconnects.
export function listen(onNotice) {
  let socket;
  let delay = 1000;
  let stopped = false;
  const connect = () => {
    const url = new URL("api/ws", base);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(url);
    socket.onopen = () => {
      delay = 1000;
    };
    socket.onmessage = (event) => {
      const notice = JSON.parse(event.data);
      if (notice.type !== "hello") onNotice(notice.type);
    };
    socket.onclose = () => {
      if (stopped) return;
      setTimeout(connect, delay);
      delay = Math.min(delay * 2, 30000);
    };
  };
  connect();
  return () => {
    stopped = true;
    socket?.close();
  };
}
