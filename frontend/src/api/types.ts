export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface StreamProfile {
  id?: number;
  kind: "main" | "sub";
  codec: string;
  resolution: string;
  fps: number;
  bitrate_kbps: number;
  rtsp_transport: string;
}

export interface PlaybackUrls {
  webrtc: string;
  hls: string;
  rtsp: string;
  /** Native codec of the camera; h265 streams are transcoded for webrtc/hls. */
  codec?: "h264" | "h265";
}

export type RecordMode = "off" | "continuous" | "motion" | "scheduled";

export interface TimeWindow {
  from: string; // "HH:MM"
  to: string; // "HH:MM"
}
/** Weekly windows for scheduled mode: keys "0".."6" (0 = Saturday). */
export type WeeklyWindows = Record<string, TimeWindow[]>;

/** Write-only policy sent with a camera so its schedule is created atomically. */
export interface RecordingPolicy {
  mode: RecordMode;
  retention_days: number;
  segment_seconds?: number;
  weekly?: WeeklyWindows;
}

/** Structured connectivity result from /cameras/test[-connection]. */
export interface ProbeResult {
  ok: boolean;
  reachable: boolean;
  reason:
    | "ok"
    | "unsupported_codec"
    | "auth"
    | "dns"
    | "network"
    | "timeout"
    | "ffprobe_missing"
    | "invalid"
    | "forbidden"
    | "unknown";
  codec?: string | null;
  width?: number | null;
  height?: number | null;
  detail?: string;
  source?: string;
}

export interface Camera {
  id: number;
  name: string;
  location: string;
  enabled: boolean;
  protocol: string;
  host: string;
  port: number;
  path: string;
  rtsp_url: string;
  username: string;
  password?: string;
  onvif_host: string;
  onvif_port: number;
  onvif_enabled: boolean;
  manufacturer: string;
  model: string;
  status: "online" | "offline" | "unknown" | "disabled";
  last_seen: string | null;
  ptz_enabled: boolean;
  thumbnail: string | null;
  is_recording: boolean;
  /** True recording mode from the camera's schedule (read-only). */
  record_mode?: RecordMode;
  /** Effective recording state (schedule OR active manual session). */
  recording_active?: boolean;
  /** Whether an operator-controlled manual session is currently recording. */
  manual_recording?: boolean;
  /** Write-only: recording policy applied atomically on create/update. */
  recording?: RecordingPolicy;
  stream_profiles: StreamProfile[];
  ptz_presets: { id: number; name: string; token: string }[];
  playback: PlaybackUrls;
}

export interface RecordingSchedule {
  id: number;
  camera: number;
  camera_name?: string;
  mode: "off" | "continuous" | "motion" | "scheduled";
  weekly: Record<string, unknown>;
  retention_days: number;
  segment_seconds: number;
  pre_event_seconds: number;
  post_event_seconds: number;
}

/** Effective recording state returned by /cameras/{id}/recording/status. */
export interface RecordingStatus {
  recording: boolean;
  mode: RecordMode;
  manual: boolean;
  session: { id: number; started_at: string; started_by: string | null } | null;
}

/** One recorded segment for the playback timeline (no pagination). */
export interface TimelineSegment {
  id: number;
  start: string;
  end: string | null;
  duration: number;
  size: number;
  has_motion: boolean;
  stream_url: string;
}

export interface Recording {
  id: number;
  camera: number;
  camera_name: string;
  start: string;
  end: string | null;
  duration: number;
  size: number;
  status: number;
  has_motion: boolean;
  stream_url: string;
}

export interface EventClipSummary {
  id: number;
  status: "pending" | "assembling" | "ready" | "failed";
  duration: number;
  error: string;
  stream_url: string | null;
}

export interface VmsEvent {
  id: number;
  camera: number | null;
  camera_name: string | null;
  type: string;
  severity: "info" | "warning" | "critical";
  details: Record<string, unknown>;
  snapshot: string | null;
  ts: string;
  acknowledged: boolean;
  ack_by_name?: string;
  cleared: boolean;
  assigned_to?: number | null;
  assigned_to_name?: string;
  comment_count?: number;
  /** Event clip (pre/post-event video), when the camera was recording. */
  clip?: EventClipSummary | null;
}

export interface EventComment {
  id: number;
  event: number;
  username?: string;
  text: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  username?: string;
  action: string;
  target: string;
  ip?: string | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Role {
  id: number;
  name: string;
  description: string;
  permissions: string[];
  is_system: boolean;
  user_count: number;
}

export interface AppUser {
  id: number;
  username: string;
  email: string;
  display_name: string;
  phone: string;
  role: number | null;
  role_name?: string;
  is_active: boolean;
  is_superuser: boolean;
  permissions: string[];
  password?: string;
}

// ---- Phase 2 ----
export interface AnalyticsRule {
  id: number;
  camera: number;
  camera_name?: string;
  kind: "motion" | "object" | "alpr";
  enabled: boolean;
  config: Record<string, unknown>;
  interval_seconds: number;
}

export interface PlateRead {
  id: number;
  camera: number;
  camera_name: string;
  plate: string;
  confidence: number;
  country: string;
  snapshot: string | null;
  watchlist_hit: boolean;
  ts: string;
}

export interface ObjectDetection {
  id: number;
  camera: number;
  camera_name: string;
  label: string;
  confidence: number;
  bbox: number[];
  snapshot: string | null;
  ts: string;
}

export interface PlateWatchlistItem {
  id: number;
  plate: string;
  reason: string;
  active: boolean;
}

export interface Door {
  id: number;
  name: string;
  location: string;
  controller_url: string;
  relay: number;
  unlock_seconds: number;
  state: "locked" | "unlocked" | "held" | "offline";
  camera: number | null;
  camera_name?: string;
}

export interface Credential {
  id: number;
  cardholder: number;
  kind: "card" | "pin" | "plate";
  value: string;
  active: boolean;
}

export interface Cardholder {
  id: number;
  first_name: string;
  last_name: string;
  employee_id: string;
  active: boolean;
  photo: string | null;
  credentials: Credential[];
}

export interface AccessEvent {
  id: number;
  door: number;
  door_name: string;
  cardholder_name: string;
  credential_value: string;
  decision: "granted" | "denied";
  reason: string;
  ts: string;
}

export interface MapMarker {
  id: number;
  site_map: number;
  kind: "camera" | "door";
  object_id: number;
  label: string;
  x: number;
  y: number;
  rotation: number;
}

export interface SiteMap {
  id: number;
  name: string;
  image: string;
  order: number;
  markers: MapMarker[];
}

export interface FederatedServer {
  id: number;
  name: string;
  base_url: string;
  username: string;
  status: "online" | "offline" | "unknown";
  last_sync: string | null;
  camera_count: number;
  enabled: boolean;
  remote_cameras: {
    id: number;
    remote_id: number;
    name: string;
    status: string;
    webrtc_url: string;
    hls_url: string;
  }[];
}

export interface EvidenceItem {
  id: number;
  kind: "recording" | "export" | "snapshot" | "note";
  camera_name?: string;
  recording: number | null;
  sha256: string;
  note: string;
  added_by_name?: string;
  added_at: string;
}

export interface EvidenceCase {
  id: number;
  case_number: string;
  title: string;
  description: string;
  status: "open" | "closed" | "archived";
  created_by_name?: string;
  item_count: number;
  items: EvidenceItem[];
  custody: { id: number; username: string; action: string; note: string; ts: string }[];
  created_at: string;
}

export type DeskTileKind = "camera" | "door" | "map";

export interface DeskTile {
  index: number;
  kind: DeskTileKind;
  object_id: number;
}

export interface DeskLayout {
  id: number;
  name: string;
  tile_count: number;
  tiles: DeskTile[];
  is_default: boolean;
  updated_at?: string;
}

export interface NotifyRecipient {
  name: string;
  phone: string;
  sms: boolean;
  call: boolean;
  active: boolean;
}

export interface NotificationSettings {
  provider: "console" | "kavenegar" | "twilio";
  kavenegar_api_key: string;
  sms_sender: string;
  twilio_sid: string;
  twilio_token: string;
  twilio_from: string;
  recipients: NotifyRecipient[];
  updated_at?: string;
}

export interface HeatmapData {
  w: number;
  h: number;
  grid: number[][];
  max: number;
  samples: number;
  days: number;
}

export interface AutomationRule {
  id: number;
  name: string;
  enabled: boolean;
  event_type: string;
  min_severity: "info" | "warning" | "critical";
  camera: number | null;
  camera_name?: string;
  action: "webhook" | "unlock_door" | "lock_door" | "set_threat";
  params: Record<string, unknown>;
  last_run: string | null;
  run_count: number;
}

export interface SystemHealth {
  services: { database: boolean; redis: boolean; mediamtx: boolean; celery: boolean };
  disk: { total: number; used: number; free: number };
  recordings: { count: number; bytes: number };
  storage_by_camera: { camera: number; name: string; bytes: number }[];
  projected_days: number | null;
  recording_delay_seconds: number | null;
  cameras: Record<string, number>;
  time: string;
}

export interface ExportJob {
  id: number;
  camera: number;
  camera_name?: string;
  start: string;
  end: string;
  status: "pending" | "running" | "done" | "failed";
  size: number;
  sha256: string;
  download_url: string | null;
  note: string;
  created_at: string;
}

export interface Bookmark {
  id: number;
  camera: number;
  camera_name?: string;
  start: string;
  end: string | null;
  note: string;
  created_at: string;
}

export interface DashboardSummary {
  threat_level: "green" | "yellow" | "red";
  cameras: {
    total: number;
    online: number;
    offline: number;
    disabled: number;
    recording: number;
  };
  events_24h: number;
  unacknowledged: number;
  recordings_total: number;
  storage_bytes: number;
}
