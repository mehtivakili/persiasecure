import { api } from "./api";
import type {
  AppUser,
  AuditLogEntry,
  Camera,
  DashboardSummary,
  EventComment,
  ExportJob,
  Paginated,
  ProbeResult,
  Recording,
  RecordingSchedule,
  RecordingStatus,
  Role,
  TimelineSegment,
  VmsEvent,
} from "./types";

export interface EventFilters {
  acknowledged?: boolean;
  camera?: number;
  type?: string;
  severity?: string;
  q?: string;
  has_clip?: boolean;
  after?: string;
  before?: string;
}

const list = <T>(r: Paginated<T> | T[]): T[] => (Array.isArray(r) ? r : r.results);

export const endpoints = api.injectEndpoints({
  endpoints: (build) => ({
    // ---- Auth ----
    login: build.mutation<
      { access: string; refresh: string; user: any },
      { username: string; password: string }
    >({
      query: (body) => ({ url: "/auth/token/", method: "POST", body }),
    }),
    me: build.query<any, void>({ query: () => "/auth/me" }),
    permissionCatalog: build.query<{ code: string; label: string }[], void>({
      query: () => "/auth/permissions",
    }),

    // ---- Dashboard ----
    dashboardSummary: build.query<DashboardSummary, void>({
      query: () => "/dashboard/summary",
      providesTags: ["Summary"],
    }),
    eventsTimeseries: build.query<{ hour: string; count: number }[], void>({
      query: () => "/dashboard/events-timeseries",
    }),

    // ---- Cameras ----
    cameras: build.query<Camera[], void>({
      query: () => "/cameras/",
      transformResponse: list<Camera>,
      providesTags: ["Camera"],
    }),
    camera: build.query<Camera, number>({
      query: (id) => `/cameras/${id}/`,
      providesTags: ["Camera"],
    }),
    createCamera: build.mutation<Camera, Partial<Camera>>({
      query: (body) => ({ url: "/cameras/", method: "POST", body }),
      invalidatesTags: ["Camera"],
    }),
    updateCamera: build.mutation<Camera, { id: number; body: Partial<Camera> }>({
      query: ({ id, body }) => ({ url: `/cameras/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Camera"],
    }),
    deleteCamera: build.mutation<void, number>({
      query: (id) => ({ url: `/cameras/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Camera"],
    }),
    testCamera: build.mutation<ProbeResult, number>({
      query: (id) => ({ url: `/cameras/${id}/test/`, method: "POST" }),
    }),
    // Pre-save connectivity test used by the onboarding wizard. Accepts raw
    // connection params (new camera) or a `camera` id to reuse stored creds.
    testConnection: build.mutation<ProbeResult, Record<string, unknown>>({
      query: (body) => ({ url: "/cameras/test-connection/", method: "POST", body }),
    }),
    // ---- Manual recording control (Phase 2) ----
    startRecording: build.mutation<RecordingStatus, number>({
      query: (id) => ({ url: `/cameras/${id}/recording/start/`, method: "POST" }),
      invalidatesTags: ["Camera"],
    }),
    stopRecording: build.mutation<RecordingStatus, number>({
      query: (id) => ({ url: `/cameras/${id}/recording/stop/`, method: "POST" }),
      invalidatesTags: ["Camera"],
    }),
    recordingStatus: build.query<RecordingStatus, number>({
      query: (id) => `/cameras/${id}/recording/status/`,
    }),
    ptz: build.mutation<
      { ok: boolean },
      { id: number; action: string; pan?: number; tilt?: number; zoom?: number; token?: string }
    >({
      query: ({ id, ...body }) => ({ url: `/cameras/${id}/ptz/`, method: "POST", body }),
    }),
    cameraBrands: build.query<
      {
        id: string;
        label: string;
        rtsp_port: number;
        onvif_port: number;
        main: string;
        sub: string;
        note: string;
      }[],
      void
    >({
      query: () => "/cameras/brands",
    }),
    onvifDiscover: build.mutation<{ devices: any[] }, { timeout?: number }>({
      query: (body) => ({ url: "/cameras/onvif/discover", method: "POST", body }),
    }),
    onvifProbe: build.mutation<
      { info: any; rtsp_url: string | null },
      { host: string; port: number; username: string; password: string }
    >({
      query: (body) => ({ url: "/cameras/onvif/probe", method: "POST", body }),
    }),

    // ---- Schedules ----
    schedules: build.query<RecordingSchedule[], void>({
      query: () => "/recording-schedules/",
      transformResponse: list<RecordingSchedule>,
      providesTags: ["Schedule"],
    }),
    updateSchedule: build.mutation<
      RecordingSchedule,
      { id: number; body: Partial<RecordingSchedule> }
    >({
      query: ({ id, body }) => ({
        url: `/recording-schedules/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: ["Schedule", "Camera"],
    }),

    // ---- Recordings ----
    recordings: build.query<Recording[], { camera?: number; after?: string; before?: string }>({
      query: (params) => ({ url: "/recordings/", params }),
      transformResponse: list<Recording>,
      providesTags: ["Recording"],
    }),
    // Full-day segment list (no pagination) so playback shows a whole day, not
    // just the first API page.
    recordingsTimeline: build.query<
      TimelineSegment[],
      { camera: number; after: string; before: string }
    >({
      query: (params) => ({ url: "/recordings/timeline/", params }),
      providesTags: ["Recording"],
    }),
    createExport: build.mutation<
      any,
      { camera: number; start: string; end: string; note?: string }
    >({
      query: (body) => ({ url: "/exports/", method: "POST", body }),
    }),
    exportJobs: build.query<ExportJob[], void>({
      query: () => "/exports/",
      transformResponse: list<ExportJob>,
    }),

    // ---- Events ----
    events: build.query<VmsEvent[], EventFilters | void>({
      query: (params) => ({ url: "/events/", params: params || undefined }),
      transformResponse: list<VmsEvent>,
      providesTags: ["Event"],
    }),
    // ---- Event investigation (Phase 5) ----
    assignEvent: build.mutation<VmsEvent, { id: number; user: number | null }>({
      query: ({ id, user }) => ({ url: `/events/${id}/assign/`, method: "POST", body: { user } }),
      invalidatesTags: ["Event"],
    }),
    eventComments: build.query<EventComment[], number>({
      query: (id) => `/events/${id}/comments/`,
      providesTags: ["Event"],
    }),
    addEventComment: build.mutation<EventComment, { id: number; text: string }>({
      query: ({ id, text }) => ({ url: `/events/${id}/comments/`, method: "POST", body: { text } }),
      invalidatesTags: ["Event"],
    }),
    relatedEvents: build.query<VmsEvent[], number>({
      query: (id) => `/events/${id}/related/`,
    }),
    reportEvent: build.mutation<
      VmsEvent,
      { id: number; false_positive?: boolean; validated?: boolean }
    >({
      query: ({ id, ...body }) => ({ url: `/events/${id}/report/`, method: "POST", body }),
      invalidatesTags: ["Event"],
    }),
    eventAudit: build.query<AuditLogEntry[], number>({
      query: (id) => `/events/${id}/audit/`,
    }),
    acknowledgeEvent: build.mutation<VmsEvent, number>({
      query: (id) => ({ url: `/events/${id}/acknowledge/`, method: "POST" }),
      invalidatesTags: ["Event"],
    }),
    clearEvent: build.mutation<VmsEvent, number>({
      query: (id) => ({ url: `/events/${id}/clear/`, method: "POST" }),
      invalidatesTags: ["Event"],
    }),
    acknowledgeAll: build.mutation<{ acknowledged: number }, void>({
      query: () => ({ url: "/events/acknowledge_all/", method: "POST" }),
      invalidatesTags: ["Event"],
    }),
    // Manual event — a convenient trigger to produce a test event clip.
    createEvent: build.mutation<
      VmsEvent,
      { camera: number; severity?: string; details?: Record<string, unknown> }
    >({
      query: (body) => ({ url: "/events/", method: "POST", body }),
      invalidatesTags: ["Event"],
    }),
    retryEventClip: build.mutation<unknown, number>({
      query: (id) => ({ url: `/event-clips/${id}/retry/`, method: "POST" }),
      invalidatesTags: ["Event"],
    }),
    protectEventClip: build.mutation<unknown, { id: number; protected_until: string | null }>({
      query: ({ id, protected_until }) => ({
        url: `/event-clips/${id}/protect/`,
        method: "POST",
        body: { protected_until },
      }),
      invalidatesTags: ["Event"],
    }),

    // ---- Users & Roles ----
    users: build.query<AppUser[], void>({
      query: () => "/users/",
      transformResponse: list<AppUser>,
      providesTags: ["User"],
    }),
    createUser: build.mutation<AppUser, Partial<AppUser>>({
      query: (body) => ({ url: "/users/", method: "POST", body }),
      invalidatesTags: ["User"],
    }),
    updateUser: build.mutation<AppUser, { id: number; body: Partial<AppUser> }>({
      query: ({ id, body }) => ({ url: `/users/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["User"],
    }),
    deleteUser: build.mutation<void, number>({
      query: (id) => ({ url: `/users/${id}/`, method: "DELETE" }),
      invalidatesTags: ["User"],
    }),
    roles: build.query<Role[], void>({
      query: () => "/roles/",
      transformResponse: list<Role>,
      providesTags: ["Role"],
    }),
    createRole: build.mutation<Role, Partial<Role>>({
      query: (body) => ({ url: "/roles/", method: "POST", body }),
      invalidatesTags: ["Role"],
    }),
    updateRole: build.mutation<Role, { id: number; body: Partial<Role> }>({
      query: ({ id, body }) => ({ url: `/roles/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Role"],
    }),
    deleteRole: build.mutation<void, number>({
      query: (id) => ({ url: `/roles/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Role"],
    }),
  }),
  overrideExisting: false,
});

export const {
  useLoginMutation,
  useMeQuery,
  usePermissionCatalogQuery,
  useDashboardSummaryQuery,
  useEventsTimeseriesQuery,
  useCamerasQuery,
  useCameraQuery,
  useCreateCameraMutation,
  useUpdateCameraMutation,
  useDeleteCameraMutation,
  useTestCameraMutation,
  useTestConnectionMutation,
  useStartRecordingMutation,
  useStopRecordingMutation,
  useRecordingStatusQuery,
  usePtzMutation,
  useCameraBrandsQuery,
  useOnvifDiscoverMutation,
  useOnvifProbeMutation,
  useSchedulesQuery,
  useUpdateScheduleMutation,
  useRecordingsQuery,
  useLazyRecordingsQuery,
  useRecordingsTimelineQuery,
  useCreateExportMutation,
  useExportJobsQuery,
  useEventsQuery,
  useAcknowledgeEventMutation,
  useClearEventMutation,
  useAcknowledgeAllMutation,
  useCreateEventMutation,
  useRetryEventClipMutation,
  useProtectEventClipMutation,
  useAssignEventMutation,
  useEventCommentsQuery,
  useAddEventCommentMutation,
  useRelatedEventsQuery,
  useReportEventMutation,
  useEventAuditQuery,
  useUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
  useRolesQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
} = endpoints;
