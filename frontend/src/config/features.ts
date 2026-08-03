import type { UserProfile } from "../features/auth/authSlice";

export type FeatureKey =
  | "analytics"
  | "access_control"
  | "maps"
  | "federation"
  | "evidence";

/** Features default closed when an old cached profile has no flag payload. */
export const featureEnabled = (user: UserProfile | null, key: FeatureKey) =>
  user?.features?.[key] === true;
