import { useMemo, useState } from "react";
import {
  Box,
  Chip,
  Collapse,
  InputAdornment,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import VideocamIcon from "@mui/icons-material/Videocam";
import MeetingRoomIcon from "@mui/icons-material/MeetingRoom";
import MapIcon from "@mui/icons-material/Map";
import ExpandMore from "@mui/icons-material/ExpandMore";
import ChevronLeft from "@mui/icons-material/ChevronLeft";
import { useTranslation } from "react-i18next";

import type { Camera, Door, SiteMap } from "../../api/types";
import type { DeskTileKind } from "../../api/types";
import CameraStatusDot from "../cameras/CameraStatusDot";

interface Props {
  cameras: Camera[];
  doors: Door[];
  maps: SiteMap[];
  /** Click-to-place fallback for touch devices (drag isn't always available). */
  onPick: (kind: DeskTileKind, id: number, label: string) => void;
}

/**
 * Genetec-style "area view": a searchable tree of every entity an operator can
 * drop into a tile. Items are HTML5-draggable; the payload is read by DeskTile.
 */
export default function EntityTree({ cameras, doors, maps, onPick }: Props) {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState({ camera: true, door: true, map: true });

  const match = (s: string) => s.toLowerCase().includes(q.trim().toLowerCase());
  const f = useMemo(
    () => ({
      cameras: cameras.filter((c) => match(c.name) || match(c.location || "")),
      doors: doors.filter((d) => match(d.name) || match(d.location || "")),
      maps: maps.filter((m) => match(m.name)),
    }),
    [cameras, doors, maps, q]
  );

  const drag = (kind: DeskTileKind, id: number) => (e: React.DragEvent) => {
    e.dataTransfer.setData("application/x-ps-entity", JSON.stringify({ kind, id }));
    e.dataTransfer.effectAllowed = "copy";
  };

  const Section = ({
    id,
    icon,
    label,
    count,
    children,
  }: {
    id: keyof typeof open;
    icon: React.ReactNode;
    label: string;
    count: number;
    children: React.ReactNode;
  }) => (
    <>
      <ListItemButton onClick={() => setOpen((o) => ({ ...o, [id]: !o[id] }))} sx={{ borderRadius: 2 }}>
        <ListItemIcon sx={{ minWidth: 34, color: "text.secondary" }}>{icon}</ListItemIcon>
        <ListItemText primaryTypographyProps={{ fontWeight: 800, fontSize: 13 }} primary={label} />
        <Chip size="small" label={count} sx={{ mr: 1 }} />
        {open[id] ? <ExpandMore fontSize="small" /> : <ChevronLeft fontSize="small" />}
      </ListItemButton>
      <Collapse in={open[id]} unmountOnExit>
        <List dense disablePadding sx={{ pr: 1 }}>
          {children}
        </List>
      </Collapse>
    </>
  );

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <TextField
        size="small"
        placeholder={t("common.search")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        sx={{ mb: 1 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
        }}
      />
      <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>
        {t("desk.dragHint")}
      </Typography>

      <Box sx={{ overflow: "auto", flexGrow: 1 }}>
        <List dense disablePadding>
          <Section id="camera" icon={<VideocamIcon />} label={t("nav.cameras")} count={f.cameras.length}>
            {f.cameras.map((c) => (
              <ListItemButton
                key={c.id}
                draggable
                onDragStart={drag("camera", c.id)}
                onClick={() => onPick("camera", c.id, c.name)}
                sx={{ borderRadius: 2, cursor: "grab" }}
              >
                <CameraStatusDot status={c.status} />
                <ListItemText
                  primaryTypographyProps={{ fontSize: 13, noWrap: true }}
                  secondaryTypographyProps={{ fontSize: 11 }}
                  primary={c.name}
                  secondary={c.location || undefined}
                />
              </ListItemButton>
            ))}
          </Section>

          <Section id="door" icon={<MeetingRoomIcon />} label={t("access.doors")} count={f.doors.length}>
            {f.doors.map((d) => (
              <ListItemButton
                key={d.id}
                draggable
                onDragStart={drag("door", d.id)}
                onClick={() => onPick("door", d.id, d.name)}
                sx={{ borderRadius: 2, cursor: "grab" }}
              >
                <ListItemIcon sx={{ minWidth: 30 }}>
                  <MeetingRoomIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primaryTypographyProps={{ fontSize: 13, noWrap: true }} primary={d.name} />
              </ListItemButton>
            ))}
          </Section>

          <Section id="map" icon={<MapIcon />} label={t("nav.maps")} count={f.maps.length}>
            {f.maps.map((m) => (
              <ListItemButton
                key={m.id}
                draggable
                onDragStart={drag("map", m.id)}
                onClick={() => onPick("map", m.id, m.name)}
                sx={{ borderRadius: 2, cursor: "grab" }}
              >
                <ListItemIcon sx={{ minWidth: 30 }}>
                  <MapIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primaryTypographyProps={{ fontSize: 13, noWrap: true }} primary={m.name} />
              </ListItemButton>
            ))}
          </Section>
        </List>
      </Box>
    </Box>
  );
}
