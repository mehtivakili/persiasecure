import { createContext, useCallback, useContext, useRef, useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
} from "@mui/material";
import { useTranslation } from "react-i18next";

/**
 * Promise-based replacement for window.confirm / window.prompt so the app uses
 * themed, RTL, accessible MUI dialogs instead of native browser popups
 * (Phase 1 UX). Mount <ConfirmProvider> once near the app root, then call
 * useConfirm() / usePrompt() from any component.
 */

interface ConfirmOptions {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

interface PromptOptions {
  title?: string;
  message?: string;
  label?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;
type PromptFn = (options: PromptOptions) => Promise<string | null>;

const ConfirmContext = createContext<ConfirmFn | null>(null);
const PromptContext = createContext<PromptFn | null>(null);

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used within <ConfirmProvider>");
  return ctx;
}

export function usePrompt(): PromptFn {
  const ctx = useContext(PromptContext);
  if (!ctx) throw new Error("usePrompt must be used within <ConfirmProvider>");
  return ctx;
}

type ConfirmState = ConfirmOptions & { open: boolean };
type PromptState = PromptOptions & { open: boolean; value: string };

export default function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const [confirmState, setConfirmState] = useState<ConfirmState>({ open: false, message: "" });
  const [promptState, setPromptState] = useState<PromptState>({ open: false, value: "" });
  const confirmResolver = useRef<(v: boolean) => void>();
  const promptResolver = useRef<(v: string | null) => void>();

  const confirm = useCallback<ConfirmFn>((options) => {
    setConfirmState({ ...options, open: true });
    return new Promise<boolean>((resolve) => {
      confirmResolver.current = resolve;
    });
  }, []);

  const prompt = useCallback<PromptFn>((options) => {
    setPromptState({ ...options, open: true, value: options.defaultValue ?? "" });
    return new Promise<string | null>((resolve) => {
      promptResolver.current = resolve;
    });
  }, []);

  const closeConfirm = (result: boolean) => {
    setConfirmState((s) => ({ ...s, open: false }));
    confirmResolver.current?.(result);
  };
  const closePrompt = (result: string | null) => {
    setPromptState((s) => ({ ...s, open: false }));
    promptResolver.current?.(result);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      <PromptContext.Provider value={prompt}>
        {children}

        <Dialog open={confirmState.open} onClose={() => closeConfirm(false)} maxWidth="xs" fullWidth>
          {confirmState.title && <DialogTitle>{confirmState.title}</DialogTitle>}
          <DialogContent>
            <DialogContentText>{confirmState.message}</DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => closeConfirm(false)}>
              {confirmState.cancelLabel || t("common.cancel")}
            </Button>
            <Button
              variant="contained"
              color={confirmState.destructive ? "error" : "primary"}
              onClick={() => closeConfirm(true)}
              autoFocus
            >
              {confirmState.confirmLabel || t("common.confirm")}
            </Button>
          </DialogActions>
        </Dialog>

        <Dialog
          open={promptState.open}
          onClose={() => closePrompt(null)}
          maxWidth="xs"
          fullWidth
          PaperProps={{
            component: "form",
            onSubmit: (e: React.FormEvent) => {
              e.preventDefault();
              closePrompt(promptState.value);
            },
          } as any}
        >
          {promptState.title && <DialogTitle>{promptState.title}</DialogTitle>}
          <DialogContent>
            {promptState.message && (
              <DialogContentText sx={{ mb: 2 }}>{promptState.message}</DialogContentText>
            )}
            <TextField
              autoFocus
              fullWidth
              label={promptState.label}
              value={promptState.value}
              onChange={(e) => setPromptState((s) => ({ ...s, value: e.target.value }))}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => closePrompt(null)}>
              {promptState.cancelLabel || t("common.cancel")}
            </Button>
            <Button type="submit" variant="contained">
              {promptState.confirmLabel || t("common.confirm")}
            </Button>
          </DialogActions>
        </Dialog>
      </PromptContext.Provider>
    </ConfirmContext.Provider>
  );
}
