import {
  BaseQueryFn,
  createApi,
  FetchArgs,
  fetchBaseQuery,
  FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";

import type { RootState } from "../app/store";
import { logout, setCredentials } from "../features/auth/authSlice";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

const rawBaseQuery = fetchBaseQuery({
  baseUrl: API_BASE,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.access;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  },
});

// Wrap the base query to transparently refresh an expired access token once.
const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, apiCtx, extraOptions) => {
  let result = await rawBaseQuery(args, apiCtx, extraOptions);
  if (result.error && result.error.status === 401) {
    const state = apiCtx.getState() as RootState;
    const refresh = state.auth.refresh;
    if (refresh) {
      const refreshResult = await rawBaseQuery(
        { url: "/auth/token/refresh/", method: "POST", body: { refresh } },
        apiCtx,
        extraOptions
      );
      const data = refreshResult.data as { access?: string } | undefined;
      if (data?.access && state.auth.user) {
        apiCtx.dispatch(
          setCredentials({ access: data.access, refresh, user: state.auth.user })
        );
        result = await rawBaseQuery(args, apiCtx, extraOptions);
      } else {
        apiCtx.dispatch(logout());
      }
    } else {
      apiCtx.dispatch(logout());
    }
  }
  return result;
};

export const api = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithReauth,
  tagTypes: [
    "Camera",
    "Recording",
    "Event",
    "User",
    "Role",
    "Schedule",
    "Bookmark",
    "AnalyticsRule",
    "PlateRead",
    "ObjectDetection",
    "Watchlist",
    "Door",
    "Cardholder",
    "AccessEvent",
    "SiteMap",
    "Federation",
    "Evidence",
    "AutomationRule",
    "Summary",
    "Health",
    "NotifySettings",
    "DeskLayout",
  ],
  endpoints: () => ({}),
});
