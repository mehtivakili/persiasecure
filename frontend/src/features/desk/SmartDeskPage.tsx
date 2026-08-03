import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import GridViewIcon from "@mui/icons-material/GridView";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import SaveIcon from "@mui/icons-material/Save";
import DeleteIcon from "@mui/icons-material/Delete";
import ClearAllIcon from "@mui/icons-material/ClearAll";
import { useTranslation } from "react-i18next";

import { useCamerasQuery, useEventsQuery } from "../../api/endpoints";
import {
  useCreateDeskLayoutMutation,
  useDeleteDeskLayoutMutation,
  useDeskLayoutsQuery,
  useUpdateDeskLayoutMutation,
} from "../../api/endpointsOps";
import { useDoorsQuery, useMapsQuery } from "../../api/endpointsPhase2";
import type { DeskTileKind } from "../../api/types";
import DeskTile, { TileContent } from "./DeskTile";
import EntityTree from "./EntityTree";
import AlarmSidebar from "./AlarmSidebar";

const LAYOUTS = [
  { key: 1, cols: 1 },
  { key: 4, cols: 2 },
  { key: 9, cols: 3 },
  { key: 16, cols: 4 },
];

/**
 * Smart Desk — the unified operator workstation (Genetec Security Desk /
 * Milestone Smart Client equivalent): entity tree → drag into tiles → each
 * tile independently does live / instant-replay / PTZ / door control, with a
 * live alarm pane that can push alarms straight into a tile.
 */
export default function SmartDeskPage() {
  const { t } = useTranslation();
  const { data: cameras } = useCamerasQuery();
  const { data: doors } = useDoorsQuery();
  const { data: maps } = useMapsQuery();
  const { data: events } = useEventsQuery();
  const { data: layouts } = useDeskLayoutsQuery();
  const [createLayout] = useCreateDeskLayoutMutation();
  const [updateLayout] = useUpdateDeskLayoutMutation();
  const [deleteLayout] = useDeleteDeskLayoutMutation();

  const [tileCount, setTileCount] = useState(4);
  const [tiles, setTiles] = useState<Record<number, TileContent>>({});
  const [maximized, setMaximized] = useState<number | null>(null);
  const [alarmedTile, setAlarmedTile] = useState<number | null>(null);
  const [autoDisplay, setAutoDisplay] = useState(true);
  const [saveOpen, setSaveOpen] = useState(false);
  const [layoutName, setLayoutName] = useState("");
  const [activeLayout, setActiveLayout] = useState<number | "">("");
  const gridRef = useRef<HTMLDivElement>(null);
  const seenAlarm = useRef<number | null>(null);

  const cols = LAYOUTS.find((l) => l.key === tileCount)?.cols ?? 2;

  // --- tile mutations ----------------------------------------------------
  const placeAt = useCallback((index: number, kind: DeskTileKind, id: number) => {
    setTiles((prev) => ({ ...prev, [index]: { kind, object_id: id } }));
  }, []);

  /** First empty tile, else tile 0 — used by click-to-place and alarms. */
  const firstFree = useCallback(() => {
    for (let i = 0; i < tileCount; i++) if (!tiles[i]) return i;
    return 0;
  }, [tiles, tileCount]);

  const pick = (kind: DeskTileKind, id: number) => placeAt(firstFree(), kind, id);

  const clearTile = (index: number) =>
    setTiles((prev) => {
      const next = { ...prev };
      delete next[index];
      return next;
    });

  const clearAll = () => setTiles({});

  // --- alarm → tile (Genetec "alarm monitoring") -------------------------
  const showCamera = useCallback(
    (cameraId: number) => {
      // Reuse the tile already showing this camera, else take the first free.
      const existing = Object.entries(tiles).find(
        ([, c]) => c.kind === "camera" && c.object_id === cameraId
      );
      const idx = existing ? Number(existing[0]) : firstFree();
      placeAt(idx, "camera", cameraId);
      setAlarmedTile(idx);
      window.setTimeout(() => setAlarmedTile((v) => (v === idx ? null : v)), 6000);
    },
    [tiles, firstFree, placeAt]
  );

  // Auto-display the newest unacknowledged alarm's camera.
  useEffect(() => {
    if (!autoDisplay || !events?.length) return;
    const newest = events.find((e) => !e.acknowledged && !e.cleared && e.camera);
    if (!newest || seenAlarm.current === newest.id) return;
    seenAlarm.current = newest.id;
    showCamera(newest.camera!);
  }, [events, autoDisplay, showCamera]);

  // --- saved layouts -----------------------------------------------------
  const tilesArray = useMemo(
    () =>
      Object.entries(tiles).map(([index, c]) => ({
        index: Number(index),
        kind: c.kind,
        object_id: c.object_id,
      })),
    [tiles]
  );

  const loadLayout = (id: number | "") => {
    setActiveLayout(id);
    const l = layouts?.find((x) => x.id === id);
    if (!l) return;
    setTileCount(l.tile_count);
    const next: Record<number, TileContent> = {};
    l.tiles.forEach((tl) => (next[tl.index] = { kind: tl.kind, object_id: tl.object_id }));
    setTiles(next);
  };

  const saveLayout = async () => {
    const body = { name: layoutName, tile_count: tileCount, tiles: tilesArray };
    const existing = layouts?.find((l) => l.name === layoutName);
    if (existing) await updateLayout({ id: existing.id, body });
    else await createLayout(body);
    setSaveOpen(false);
    setLayoutName("");
  };

  const goWall = () => gridRef.current?.requestFullscreen?.();

  // Maximized view: show a single tile full-width.
  const visibleTiles = maximized !== null ? [maximized] : Array.from({ length: tileCount }, (_, i) => i);
  const effCols = maximized !== null ? 1 : cols;

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 2 }} flexWrap="wrap">
        <Typography variant="h4">{t("desk.title")}</Typography>
        <Box sx={{ flexGrow: 1 }} />

        <TextField
          select
          size="small"
          label={t("desk.savedLayouts")}
          value={activeLayout}
          onChange={(e) => loadLayout(e.target.value === "" ? "" : Number(e.target.value))}
          sx={{ minWidth: 170 }}
        >
          <MenuItem value="">{t("desk.none")}</MenuItem>
          {(layouts || []).map((l) => (
            <MenuItem key={l.id} value={l.id}>
              {l.name}
            </MenuItem>
          ))}
        </TextField>
        {activeLayout !== "" && (
          <Tooltip title={t("common.delete")}>
            <IconButton
              size="small"
              color="error"
              onClick={() => {
                deleteLayout(Number(activeLayout));
                setActiveLayout("");
              }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Button size="small" startIcon={<SaveIcon />} onClick={() => setSaveOpen(true)}>
          {t("desk.saveLayout")}
        </Button>
        <Button size="small" startIcon={<ClearAllIcon />} onClick={clearAll}>
          {t("desk.clearAll")}
        </Button>
        <Button size="small" variant="outlined" startIcon={<FullscreenIcon />} onClick={goWall}>
          {t("liveview.wall")}
        </Button>

        <GridViewIcon color="disabled" />
        <ToggleButtonGroup
          size="small"
          exclusive
          value={tileCount}
          onChange={(_e, v) => {
            if (v) {
              setTileCount(v);
              setMaximized(null);
            }
          }}
        >
          {LAYOUTS.map((l) => (
            <ToggleButton key={l.key} value={l.key}>
              {l.key}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>

      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", minWidth: 0 }}>
        {/* Entity tree */}
        <Card sx={{ width: 250, flexShrink: 0, p: 1.5, height: "76vh" }}>
          <EntityTree
            cameras={cameras || []}
            doors={doors || []}
            maps={maps || []}
            onPick={(kind, id) => pick(kind, id)}
          />
        </Card>

        {/* Tile canvas */}
        <Box
          ref={gridRef}
          sx={{
            flex: 1,
            minWidth: 0,
            display: "grid",
            gridTemplateColumns: `repeat(${effCols}, 1fr)`,
            gap: 1.25,
            bgcolor: "#05070a",
            p: 1,
            borderRadius: 2,
          }}
        >
          {visibleTiles.map((i) => (
            <DeskTile
              key={i}
              index={i}
              content={tiles[i] || null}
              cameras={cameras || []}
              doors={doors || []}
              maps={maps || []}
              onDrop={placeAt}
              onClear={clearTile}
              onMaximize={(idx) => setMaximized((m) => (m === idx ? null : idx))}
              alarmed={alarmedTile === i}
            />
          ))}
        </Box>

        {/* Alarm pane */}
        <Card sx={{ width: 260, flexShrink: 0, p: 1.5, height: "76vh" }}>
          <AlarmSidebar
            events={events || []}
            autoDisplay={autoDisplay}
            onAutoDisplayChange={setAutoDisplay}
            onShow={showCamera}
          />
        </Card>
      </Box>

      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>{t("desk.saveLayout")}</DialogTitle>
        <DialogContent dividers>
          <TextField
            autoFocus
            fullWidth
            label={t("desk.layoutName")}
            value={layoutName}
            onChange={(e) => setLayoutName(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveOpen(false)}>{t("common.cancel")}</Button>
          <Button variant="contained" onClick={saveLayout} disabled={!layoutName}>
            {t("common.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
