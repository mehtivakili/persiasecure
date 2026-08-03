import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import GppGoodIcon from "@mui/icons-material/GppGood";
import VerifiedIcon from "@mui/icons-material/Verified";
import FolderIcon from "@mui/icons-material/Folder";
import NoteAddIcon from "@mui/icons-material/NoteAdd";
import { useTranslation } from "react-i18next";

import {
  useAddNoteToCaseMutation,
  useCloseCaseMutation,
  useCreateEvidenceCaseMutation,
  useEvidenceCasesQuery,
  useVerifyCaseMutation,
} from "../../api/endpointsPhase2";
import { formatDateTime } from "../../utils/format";

const statusColor: Record<string, "info" | "default" | "warning"> = {
  open: "info",
  closed: "default",
  archived: "warning",
};

export default function EvidencePage() {
  const { t } = useTranslation();
  const { data: cases } = useEvidenceCasesQuery();
  const [createCase] = useCreateEvidenceCaseMutation();
  const [addNote] = useAddNoteToCaseMutation();
  const [closeCase] = useCloseCaseMutation();
  const [verify] = useVerifyCaseMutation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ case_number: "", title: "", description: "" });
  const [selected, setSelected] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [verifyResult, setVerifyResult] = useState<string | null>(null);

  const active = (cases || []).find((c) => c.id === selected) || null;

  const doVerify = async (id: number) => {
    const res = await verify(id).unwrap();
    const intact = res.results.filter((r) => r.intact).length;
    setVerifyResult(`${intact}/${res.results.length}`);
  };

  return (
    <Box>
      <Stack direction="row" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4">{t("evidence.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          {t("evidence.addCase")}
        </Button>
      </Stack>

      <Grid container spacing={2}>
        <Grid item xs={12} md={5}>
          <Stack spacing={1}>
            {(cases || []).map((c) => (
              <Card
                key={c.id}
                onClick={() => { setSelected(c.id); setVerifyResult(null); }}
                sx={{
                  border: selected === c.id ? "2px solid #2e9bff" : "1px solid #2b3a4f",
                  cursor: "pointer",
                }}
              >
                <CardContent sx={{ py: 1.5 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <FolderIcon color="disabled" />
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography>{c.title}</Typography>
                      <Typography variant="caption" color="text.secondary" dir="ltr">
                        {c.case_number}
                      </Typography>
                    </Box>
                    <Chip size="small" color={statusColor[c.status]} label={t(`evidence.status.${c.status}`)} />
                    <Chip size="small" variant="outlined" label={c.item_count} />
                  </Stack>
                </CardContent>
              </Card>
            ))}
            {!cases?.length && <Typography color="text.secondary">{t("evidence.empty")}</Typography>}
          </Stack>
        </Grid>

        <Grid item xs={12} md={7}>
          {active ? (
            <Card sx={{ border: "1px solid #2b3a4f" }}>
              <CardContent>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                  <GppGoodIcon color="primary" />
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    {active.title}
                  </Typography>
                  <Button size="small" startIcon={<VerifiedIcon />} onClick={() => doVerify(active.id)}>
                    {t("evidence.verify")}
                  </Button>
                  {active.status === "open" && (
                    <Button size="small" color="warning" onClick={() => closeCase(active.id)}>
                      {t("evidence.close")}
                    </Button>
                  )}
                </Stack>
                {verifyResult && (
                  <Chip color="success" icon={<VerifiedIcon />} label={`${t("evidence.integrity")}: ${verifyResult}`} sx={{ mb: 1 }} />
                )}
                <Typography variant="body2" color="text.secondary">
                  {active.description}
                </Typography>

                <Typography variant="subtitle2" sx={{ mt: 2 }}>
                  {t("evidence.items")}
                </Typography>
                <List dense>
                  {active.items.map((it) => (
                    <ListItem key={it.id} sx={{ px: 0 }}>
                      <ListItemIcon sx={{ minWidth: 34 }}>
                        {it.kind === "note" ? <NoteAddIcon fontSize="small" /> : <FolderIcon fontSize="small" />}
                      </ListItemIcon>
                      <ListItemText
                        primary={it.kind === "note" ? it.note : `${t(`evidence.kind.${it.kind}`)} — ${it.camera_name || ""}`}
                        secondary={it.sha256 ? `SHA256: ${it.sha256.slice(0, 16)}…` : formatDateTime(it.added_at)}
                        secondaryTypographyProps={{ sx: { fontFamily: "monospace" } }}
                      />
                    </ListItem>
                  ))}
                </List>

                {active.status === "open" && (
                  <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                    <TextField size="small" fullWidth placeholder={t("evidence.addNote")} value={note} onChange={(e) => setNote(e.target.value)} />
                    <Button
                      variant="outlined"
                      disabled={!note}
                      onClick={async () => { await addNote({ id: active.id, note }); setNote(""); }}
                    >
                      {t("common.save")}
                    </Button>
                  </Stack>
                )}

                <Divider sx={{ my: 2, borderColor: "#2b3a4f" }} />
                <Typography variant="subtitle2">{t("evidence.custody")}</Typography>
                <List dense>
                  {active.custody.map((cl) => (
                    <ListItem key={cl.id} sx={{ px: 0 }}>
                      <ListItemText primary={`${cl.username} — ${cl.action}`} secondary={formatDateTime(cl.ts)} />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>
          ) : (
            <Typography color="text.secondary">{t("evidence.selectCase")}</Typography>
          )}
        </Grid>
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{t("evidence.addCase")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label={t("evidence.caseNumber")} dir="ltr" value={form.case_number} onChange={(e) => setForm({ ...form, case_number: e.target.value })} />
            <TextField label={t("evidence.caseTitle")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <TextField label={t("evidence.description")} multiline rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={async () => { await createCase(form); setOpen(false); }} disabled={!form.case_number || !form.title}>
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
