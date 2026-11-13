"""Build a KiCad board from a schematic description and a placement table.

The schematic object already knows every pin's net.  This places the
footprints, pours ground on every copper layer, hands the board to the
freerouting autorouter and reads the result back, then runs KiCad's design
rule check.  Placement is the part that carries the design intent; the
routing is a first pass to be reviewed, not a finished layout.
"""
import json
import os
import subprocess

import pcbnew

FPDIR = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FREEROUTING = os.environ.get("FREEROUTING", os.path.join(
    ROOT, "tools/freerouting/freerouting-2.5.0-linux-x64/bin/freerouting"))

mm = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


class Board:
    def __init__(self, sch, width, height, layers=4, track=0.25, clearance=0.2,
                 via=(0.6, 0.3), pad_alias=None):
        self.sch = sch
        self.w, self.h = width, height
        self.layers = layers
        self.rules = dict(track=track, clearance=clearance, via=via)
        self.placed = {}
        self.pad_alias = pad_alias or {}     # footprint pad number -> schematic pin number
        self.keepouts = []

    def place(self, ref, x, y, rot=0, side="F"):
        self.placed[ref] = (x, y, rot, side)

    # ------------------------------------------------------------------
    def build(self, outdir):
        b = pcbnew.BOARD()
        b.SetCopperLayerCount(self.layers)
        ds = b.GetDesignSettings()
        ds.m_TrackMinWidth = mm(0.127)
        ds.m_MinClearance = mm(0.127)
        ds.m_ViasMinSize = mm(0.45)
        ds.m_MinThroughDrill = mm(0.2)
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetTrackWidth(mm(self.rules["track"]))
        nc.SetClearance(mm(self.rules["clearance"]))
        nc.SetViaDiameter(mm(self.rules["via"][0]))
        nc.SetViaDrill(mm(self.rules["via"][1]))

        nets = {}
        for net in sorted({v for v in self.sch.want.values() if v}):
            ni = pcbnew.NETINFO_ITEM(b, net)
            b.Add(ni)
            nets[net] = ni

        missing = [r for r in self.sch.parts if r not in self.placed]
        if missing:
            raise ValueError("not placed: " + " ".join(sorted(missing)))
        self.unmapped = []
        for ref, (x, y, rot, side) in self.placed.items():
            part = self.sch.parts[ref]
            lib, name = part["fp"].split(":")
            fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + ".pretty"), name)
            if fp is None:
                raise ValueError(f"{ref}: footprint {part['fp']} not found")
            fp.SetReference(ref)
            fp.SetValue(part["value"])
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            b.Add(fp)
            fp.SetPosition(P(x, y))
            if side == "B":
                fp.Flip(P(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            fp.SetOrientationDegrees(rot)
            for pad in fp.Pads():
                num = pad.GetNumber()
                if not num:
                    continue
                key = (ref, self.pad_alias.get((ref, num), num))
                if key in self.sch.want:
                    net = self.sch.want[key]
                    if net:
                        pad.SetNet(nets[net])
                else:
                    self.unmapped.append(f"{ref}.{num}")

        # outline
        pts = [(0, 0), (self.w, 0), (self.w, self.h), (0, self.h)]
        for i in range(4):
            seg = pcbnew.PCB_SHAPE(b)
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(P(*pts[i]))
            seg.SetEnd(P(*pts[(i + 1) % 4]))
            seg.SetLayer(pcbnew.Edge_Cuts)
            seg.SetWidth(mm(0.1))
            b.Add(seg)

        # Ground planes on the inner layers and the back.  The top layer gets
        # its pour only after routing, so the router has to take every ground
        # pad down to a plane with a via instead of counting on the pour.
        self._pts, self._gnd = pts, nets["GND"]
        copper = [pcbnew.B_Cu]
        if self.layers == 4:
            copper += [pcbnew.In1_Cu, pcbnew.In2_Cu]
        for layer in copper:
            self._zone(b, layer)

        os.makedirs(outdir, exist_ok=True)
        self.board = b
        self.path = os.path.join(outdir, self.sch.name + ".kicad_pcb")
        pcbnew.SaveBoard(self.path, b)
        return self.path

    def _zone(self, b, layer):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(self._gnd)
        z.SetLocalClearance(mm(0.25))
        z.SetMinThickness(mm(0.2))
        # solid connections: thermal spokes starve the small ground pads
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        o = z.Outline()
        o.NewOutline()
        for x, y in self._pts:
            o.Append(mm(x), mm(y))
        b.Add(z)

    def top_pour(self):
        self._zone(self.board, pcbnew.F_Cu)
        pcbnew.SaveBoard(self.path, self.board)

    def route(self, workdir, passes=20):
        os.makedirs(workdir, exist_ok=True)
        dsn = os.path.join(workdir, self.sch.name + ".dsn")
        ses = os.path.join(workdir, self.sch.name + ".ses")
        for f in (dsn, ses):
            if os.path.exists(f):
                os.remove(f)
        if not pcbnew.ExportSpecctraDSN(self.board, dsn):
            raise RuntimeError("DSN export failed")
        # The router needs no network; give it none.
        cmd = [FREEROUTING, "-de", dsn, "-do", ses, "-mp", str(passes), "-mt", "8",
               "--gui.enabled=false"]
        if subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0:
            cmd = ["unshare", "-rn"] + cmd
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        self.route_log = "\n".join(l[25:] for l in r.stdout.splitlines() if "DEBUG" not in l)[-1500:]
        if not os.path.exists(ses):
            raise RuntimeError("autorouter produced nothing:\n" + self.route_log)
        if not pcbnew.ImportSpecctraSES(self.board, ses):
            raise RuntimeError("SES import failed")
        self.top_pour()

    def drc(self, workdir):
        os.makedirs(workdir, exist_ok=True)
        rpt = os.path.join(workdir, self.sch.name + "-drc.json")
        # kicad-cli fills the zones and saves: filling from Python crashes
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                        "--refill-zones", "--save-board", "-o", rpt, self.path],
                       capture_output=True, text=True)
        with open(rpt) as f:
            d = json.load(f)
        out = {"violations": [], "unconnected": []}
        for v in d.get("violations", []):
            out["violations"].append((v.get("severity"), v.get("type"), v.get("description"),
                                      "; ".join(i.get("description", "") for i in v.get("items", []))))
        for v in d.get("unconnected_items", []):
            out["unconnected"].append("; ".join(i.get("description", "") for i in v.get("items", [])))
        return out

    def render(self, outdir, side="top"):
        out = os.path.join(outdir, f"{self.sch.name}-{side}.png")
        subprocess.run(["kicad-cli", "pcb", "render", "--side", side, "--width", "1600",
                        "--height", "1000", "--quality", "basic", "-o", out, self.path],
                       capture_output=True, text=True)
        return out

    def svg(self, outdir, layers="F.Cu,F.SilkS,Edge.Cuts", name="top"):
        out = os.path.join(outdir, f"{self.sch.name}-{name}.svg")
        subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", layers,
                        "--mode-single", "--page-size-mode", "2", "--exclude-drawing-sheet",
                        "-o", out, self.path], capture_output=True, text=True)
        return out
