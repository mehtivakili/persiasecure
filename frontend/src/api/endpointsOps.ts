import { api } from "./api";
import type {
  AutomationRule,
  Bookmark,
  DeskLayout,
  NotificationSettings,
  Paginated,
  SystemHealth,
} from "./types";

const list = <T>(r: Paginated<T> | T[]): T[] => (Array.isArray(r) ? r : r.results);

/** Operations endpoints: automation rules, threat level, health, bookmarks. */
export const ops = api.injectEndpoints({
  endpoints: (build) => ({
    automationRules: build.query<AutomationRule[], void>({
      query: () => "/automation-rules/",
      transformResponse: list<AutomationRule>,
      providesTags: ["AutomationRule"],
    }),
    createAutomationRule: build.mutation<AutomationRule, Partial<AutomationRule>>({
      query: (body) => ({ url: "/automation-rules/", method: "POST", body }),
      invalidatesTags: ["AutomationRule"],
    }),
    updateAutomationRule: build.mutation<
      AutomationRule,
      { id: number; body: Partial<AutomationRule> }
    >({
      query: ({ id, body }) => ({ url: `/automation-rules/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["AutomationRule"],
    }),
    deleteAutomationRule: build.mutation<void, number>({
      query: (id) => ({ url: `/automation-rules/${id}/`, method: "DELETE" }),
      invalidatesTags: ["AutomationRule"],
    }),

    setThreatLevel: build.mutation<{ threat_level: string }, string>({
      query: (level) => ({ url: "/org/threat-level", method: "POST", body: { level } }),
      invalidatesTags: ["Summary"],
    }),

    systemHealth: build.query<SystemHealth, void>({
      query: () => "/system/health",
      providesTags: ["Health"],
    }),

    notificationSettings: build.query<NotificationSettings, void>({
      query: () => "/settings/notifications",
      providesTags: ["NotifySettings"],
    }),
    updateNotificationSettings: build.mutation<NotificationSettings, Partial<NotificationSettings>>({
      query: (body) => ({ url: "/settings/notifications", method: "PUT", body }),
      invalidatesTags: ["NotifySettings"],
    }),
    testNotification: build.mutation<
      { ok: boolean; provider: string },
      { phone: string; channel: "sms" | "call" }
    >({
      query: (body) => ({ url: "/settings/notifications/test", method: "POST", body }),
    }),

    // ---- Smart Desk saved layouts ----
    deskLayouts: build.query<DeskLayout[], void>({
      query: () => "/desk-layouts/",
      transformResponse: list<DeskLayout>,
      providesTags: ["DeskLayout"],
    }),
    createDeskLayout: build.mutation<DeskLayout, Partial<DeskLayout>>({
      query: (body) => ({ url: "/desk-layouts/", method: "POST", body }),
      invalidatesTags: ["DeskLayout"],
    }),
    updateDeskLayout: build.mutation<DeskLayout, { id: number; body: Partial<DeskLayout> }>({
      query: ({ id, body }) => ({ url: `/desk-layouts/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["DeskLayout"],
    }),
    deleteDeskLayout: build.mutation<void, number>({
      query: (id) => ({ url: `/desk-layouts/${id}/`, method: "DELETE" }),
      invalidatesTags: ["DeskLayout"],
    }),

    bookmarks: build.query<Bookmark[], { camera?: number } | void>({
      query: (params) => ({ url: "/bookmarks/", params: params || undefined }),
      transformResponse: list<Bookmark>,
      providesTags: ["Bookmark"],
    }),
    createBookmark: build.mutation<Bookmark, Partial<Bookmark>>({
      query: (body) => ({ url: "/bookmarks/", method: "POST", body }),
      invalidatesTags: ["Bookmark"],
    }),
    deleteBookmark: build.mutation<void, number>({
      query: (id) => ({ url: `/bookmarks/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Bookmark"],
    }),
  }),
  overrideExisting: false,
});

export const {
  useAutomationRulesQuery,
  useCreateAutomationRuleMutation,
  useUpdateAutomationRuleMutation,
  useDeleteAutomationRuleMutation,
  useSetThreatLevelMutation,
  useSystemHealthQuery,
  useNotificationSettingsQuery,
  useUpdateNotificationSettingsMutation,
  useTestNotificationMutation,
  useDeskLayoutsQuery,
  useCreateDeskLayoutMutation,
  useUpdateDeskLayoutMutation,
  useDeleteDeskLayoutMutation,
  useBookmarksQuery,
  useCreateBookmarkMutation,
  useDeleteBookmarkMutation,
} = ops;
