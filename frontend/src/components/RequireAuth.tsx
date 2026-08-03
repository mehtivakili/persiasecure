import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAppSelector } from "../app/hooks";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const access = useAppSelector((s) => s.auth.access);
  const location = useLocation();
  if (!access) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
