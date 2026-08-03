import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface UserProfile {
  id: number;
  username: string;
  display_name: string;
  role_name?: string;
  is_superuser: boolean;
  permissions: string[];
  features?: Record<string, boolean>;
  organization?: { id: number; name: string };
}

interface AuthState {
  access: string | null;
  refresh: string | null;
  user: UserProfile | null;
}

const initialState: AuthState = {
  access: localStorage.getItem("access"),
  refresh: localStorage.getItem("refresh"),
  user: JSON.parse(localStorage.getItem("user") || "null"),
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials: (
      state,
      action: PayloadAction<{ access: string; refresh: string; user: UserProfile }>
    ) => {
      state.access = action.payload.access;
      state.refresh = action.payload.refresh;
      state.user = action.payload.user;
      localStorage.setItem("access", action.payload.access);
      localStorage.setItem("refresh", action.payload.refresh);
      localStorage.setItem("user", JSON.stringify(action.payload.user));
    },
    setUser: (state, action: PayloadAction<UserProfile>) => {
      state.user = action.payload;
      localStorage.setItem("user", JSON.stringify(action.payload));
    },
    logout: (state) => {
      state.access = null;
      state.refresh = null;
      state.user = null;
      localStorage.removeItem("access");
      localStorage.removeItem("refresh");
      localStorage.removeItem("user");
    },
  },
});

export const { setCredentials, setUser, logout } = authSlice.actions;
export default authSlice.reducer;

export const hasPerm = (user: UserProfile | null, code: string) =>
  !!user && (user.is_superuser || user.permissions.includes(code));
