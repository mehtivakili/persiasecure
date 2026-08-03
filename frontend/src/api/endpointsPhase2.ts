import { api } from "./api";
import type {
  AccessEvent,
  AnalyticsRule,
  Cardholder,
  Credential,
  Door,
  EvidenceCase,
  FederatedServer,
  HeatmapData,
  MapMarker,
  ObjectDetection,
  Paginated,
  PlateRead,
  PlateWatchlistItem,
  SiteMap,
} from "./types";

const list = <T>(r: Paginated<T> | T[]): T[] => (Array.isArray(r) ? r : r.results);

export const phase2 = api.injectEndpoints({
  endpoints: (build) => ({
    // ---- Analytics ----
    analyticsRules: build.query<AnalyticsRule[], void>({
      query: () => "/analytics-rules/",
      transformResponse: list<AnalyticsRule>,
      providesTags: ["AnalyticsRule"],
    }),
    createAnalyticsRule: build.mutation<AnalyticsRule, Partial<AnalyticsRule>>({
      query: (body) => ({ url: "/analytics-rules/", method: "POST", body }),
      invalidatesTags: ["AnalyticsRule"],
    }),
    updateAnalyticsRule: build.mutation<AnalyticsRule, { id: number; body: Partial<AnalyticsRule> }>({
      query: ({ id, body }) => ({ url: `/analytics-rules/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["AnalyticsRule"],
    }),
    deleteAnalyticsRule: build.mutation<void, number>({
      query: (id) => ({ url: `/analytics-rules/${id}/`, method: "DELETE" }),
      invalidatesTags: ["AnalyticsRule"],
    }),
    runRuleNow: build.mutation<{ queued?: boolean; detected?: boolean }, number>({
      query: (id) => ({ url: `/analytics-rules/${id}/run_now/`, method: "POST" }),
    }),
    plateReads: build.query<PlateRead[], void>({
      query: () => "/plate-reads/",
      transformResponse: list<PlateRead>,
      providesTags: ["PlateRead"],
    }),
    objectDetections: build.query<ObjectDetection[], void>({
      query: () => "/object-detections/",
      transformResponse: list<ObjectDetection>,
      providesTags: ["ObjectDetection"],
    }),
    motionHeatmap: build.query<HeatmapData, { camera: number; days?: number }>({
      query: (params) => ({ url: "/analytics/heatmap", params }),
    }),
    plateWatchlist: build.query<PlateWatchlistItem[], void>({
      query: () => "/plate-watchlist/",
      transformResponse: list<PlateWatchlistItem>,
      providesTags: ["Watchlist"],
    }),
    createWatchlistItem: build.mutation<PlateWatchlistItem, Partial<PlateWatchlistItem>>({
      query: (body) => ({ url: "/plate-watchlist/", method: "POST", body }),
      invalidatesTags: ["Watchlist"],
    }),
    deleteWatchlistItem: build.mutation<void, number>({
      query: (id) => ({ url: `/plate-watchlist/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Watchlist"],
    }),

    // ---- Access control ----
    doors: build.query<Door[], void>({
      query: () => "/doors/",
      transformResponse: list<Door>,
      providesTags: ["Door"],
    }),
    createDoor: build.mutation<Door, Partial<Door>>({
      query: (body) => ({ url: "/doors/", method: "POST", body }),
      invalidatesTags: ["Door"],
    }),
    updateDoor: build.mutation<Door, { id: number; body: Partial<Door> }>({
      query: ({ id, body }) => ({ url: `/doors/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Door"],
    }),
    deleteDoor: build.mutation<void, number>({
      query: (id) => ({ url: `/doors/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Door"],
    }),
    unlockDoor: build.mutation<{ ok: boolean }, number>({
      query: (id) => ({ url: `/doors/${id}/unlock/`, method: "POST" }),
      invalidatesTags: ["Door", "AccessEvent"],
    }),
    lockDoor: build.mutation<{ ok: boolean }, number>({
      query: (id) => ({ url: `/doors/${id}/lock/`, method: "POST" }),
      invalidatesTags: ["Door"],
    }),
    cardholders: build.query<Cardholder[], void>({
      query: () => "/cardholders/",
      transformResponse: list<Cardholder>,
      providesTags: ["Cardholder"],
    }),
    createCardholder: build.mutation<Cardholder, Partial<Cardholder>>({
      query: (body) => ({ url: "/cardholders/", method: "POST", body }),
      invalidatesTags: ["Cardholder"],
    }),
    deleteCardholder: build.mutation<void, number>({
      query: (id) => ({ url: `/cardholders/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Cardholder"],
    }),
    createCredential: build.mutation<Credential, Partial<Credential>>({
      query: (body) => ({ url: "/credentials/", method: "POST", body }),
      invalidatesTags: ["Cardholder"],
    }),
    deleteCredential: build.mutation<void, number>({
      query: (id) => ({ url: `/credentials/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Cardholder"],
    }),
    accessEvents: build.query<AccessEvent[], void>({
      query: () => "/access-events/",
      transformResponse: list<AccessEvent>,
      providesTags: ["AccessEvent"],
    }),

    // ---- Maps ----
    maps: build.query<SiteMap[], void>({
      query: () => "/maps/",
      transformResponse: list<SiteMap>,
      providesTags: ["SiteMap"],
    }),
    createMap: build.mutation<SiteMap, FormData>({
      query: (body) => ({ url: "/maps/", method: "POST", body }),
      invalidatesTags: ["SiteMap"],
    }),
    deleteMap: build.mutation<void, number>({
      query: (id) => ({ url: `/maps/${id}/`, method: "DELETE" }),
      invalidatesTags: ["SiteMap"],
    }),
    createMarker: build.mutation<MapMarker, Partial<MapMarker>>({
      query: (body) => ({ url: "/map-markers/", method: "POST", body }),
      invalidatesTags: ["SiteMap"],
    }),
    updateMarker: build.mutation<MapMarker, { id: number; body: Partial<MapMarker> }>({
      query: ({ id, body }) => ({ url: `/map-markers/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["SiteMap"],
    }),
    deleteMarker: build.mutation<void, number>({
      query: (id) => ({ url: `/map-markers/${id}/`, method: "DELETE" }),
      invalidatesTags: ["SiteMap"],
    }),

    // ---- Federation ----
    federatedServers: build.query<FederatedServer[], void>({
      query: () => "/federated-servers/",
      transformResponse: list<FederatedServer>,
      providesTags: ["Federation"],
    }),
    createFederatedServer: build.mutation<FederatedServer, Partial<FederatedServer>>({
      query: (body) => ({ url: "/federated-servers/", method: "POST", body }),
      invalidatesTags: ["Federation"],
    }),
    deleteFederatedServer: build.mutation<void, number>({
      query: (id) => ({ url: `/federated-servers/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Federation"],
    }),
    syncFederatedServer: build.mutation<{ queued: boolean }, number>({
      query: (id) => ({ url: `/federated-servers/${id}/sync/`, method: "POST" }),
      invalidatesTags: ["Federation"],
    }),

    // ---- Evidence ----
    evidenceCases: build.query<EvidenceCase[], void>({
      query: () => "/evidence-cases/",
      transformResponse: list<EvidenceCase>,
      providesTags: ["Evidence"],
    }),
    evidenceCase: build.query<EvidenceCase, number>({
      query: (id) => `/evidence-cases/${id}/`,
      providesTags: ["Evidence"],
    }),
    createEvidenceCase: build.mutation<EvidenceCase, Partial<EvidenceCase>>({
      query: (body) => ({ url: "/evidence-cases/", method: "POST", body }),
      invalidatesTags: ["Evidence"],
    }),
    addRecordingToCase: build.mutation<unknown, { id: number; recording: number }>({
      query: ({ id, recording }) => ({
        url: `/evidence-cases/${id}/add-recording/`,
        method: "POST",
        body: { recording },
      }),
      invalidatesTags: ["Evidence"],
    }),
    addNoteToCase: build.mutation<unknown, { id: number; note: string }>({
      query: ({ id, note }) => ({
        url: `/evidence-cases/${id}/add_note/`,
        method: "POST",
        body: { note },
      }),
      invalidatesTags: ["Evidence"],
    }),
    closeCase: build.mutation<EvidenceCase, number>({
      query: (id) => ({ url: `/evidence-cases/${id}/close/`, method: "POST" }),
      invalidatesTags: ["Evidence"],
    }),
    verifyCase: build.mutation<{ results: { item: number; intact: boolean }[] }, number>({
      query: (id) => ({ url: `/evidence-cases/${id}/verify/`, method: "POST" }),
    }),
  }),
  overrideExisting: false,
});

export const {
  useAnalyticsRulesQuery,
  useCreateAnalyticsRuleMutation,
  useUpdateAnalyticsRuleMutation,
  useDeleteAnalyticsRuleMutation,
  useRunRuleNowMutation,
  usePlateReadsQuery,
  useObjectDetectionsQuery,
  useMotionHeatmapQuery,
  usePlateWatchlistQuery,
  useCreateWatchlistItemMutation,
  useDeleteWatchlistItemMutation,
  useDoorsQuery,
  useCreateDoorMutation,
  useUpdateDoorMutation,
  useDeleteDoorMutation,
  useUnlockDoorMutation,
  useLockDoorMutation,
  useCardholdersQuery,
  useCreateCardholderMutation,
  useDeleteCardholderMutation,
  useCreateCredentialMutation,
  useDeleteCredentialMutation,
  useAccessEventsQuery,
  useMapsQuery,
  useCreateMapMutation,
  useDeleteMapMutation,
  useCreateMarkerMutation,
  useUpdateMarkerMutation,
  useDeleteMarkerMutation,
  useFederatedServersQuery,
  useCreateFederatedServerMutation,
  useDeleteFederatedServerMutation,
  useSyncFederatedServerMutation,
  useEvidenceCasesQuery,
  useEvidenceCaseQuery,
  useCreateEvidenceCaseMutation,
  useAddRecordingToCaseMutation,
  useAddNoteToCaseMutation,
  useCloseCaseMutation,
  useVerifyCaseMutation,
} = phase2;
