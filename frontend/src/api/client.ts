import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { TokenResponse } from "../types";

const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

let accessToken: string | null = null;
let refreshInFlight: Promise<TokenResponse | null> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function refreshSession() {
  refreshInFlight ??= axios
    .post<TokenResponse>("/api/auth/refresh", null, { withCredentials: true })
    .then(({ data }) => {
      setAccessToken(data.access_token);
      return data;
    })
    .catch(() => {
      setAccessToken(null);
      return null;
    })
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    if (
      error.response?.status !== 401 ||
      !request ||
      request._retried ||
      request.url?.includes("/auth/login") ||
      request.url?.includes("/auth/refresh")
    ) {
      return Promise.reject(error);
    }

    request._retried = true;
    const refreshed = await refreshSession();
    if (!refreshed) return Promise.reject(error);
    request.headers.Authorization = `Bearer ${refreshed.access_token}`;
    return api(request);
  },
);

export default api;
