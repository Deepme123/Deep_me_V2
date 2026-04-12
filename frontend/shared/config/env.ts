const DEFAULT_API_BASE_URL = "http://localhost:8000";
const DEFAULT_WS_BASE_URL = "ws://localhost:8000";

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function resolveWsBaseUrl(apiBaseUrl: string) {
  if (apiBaseUrl.startsWith("https://")) {
    return `wss://${apiBaseUrl.slice("https://".length)}`;
  }
  if (apiBaseUrl.startsWith("http://")) {
    return `ws://${apiBaseUrl.slice("http://".length)}`;
  }
  return apiBaseUrl;
}

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
const rawWsBaseUrl =
  import.meta.env.VITE_WS_BASE_URL ?? resolveWsBaseUrl(rawApiBaseUrl);

export const env = {
  apiBaseUrl: trimTrailingSlash(rawApiBaseUrl),
  wsBaseUrl: trimTrailingSlash(rawWsBaseUrl),
};
