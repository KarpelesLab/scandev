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
                 via=(0.6, 0.3), pad_alias=None, wide=None, wide_via=(0.8, 0.4),
                 planes=("In1.Cu",), zone_clearance=0.25):
        self.sch = sch
        self.w, self.h = width, height
        self.layers = layers
        self.rules = dict(track=track, clearance=clearance, via=via)
        self.placed = {}
        self.pad_alias = pad_alias or {}     # footprint pad number -> schematic pin number
        self.wide = wide or {}             # net -> track width, mm
        self.wide_via = wide_via
        self.zone_clearance = zone_clearance
        self.planes = planes               # ground planes present while routing
        self.edge_refs = set()             # edge-mount parts: pads reach the outline

    def place(self, ref, x, y, rot=0, side="F"):
        self.placed[ref] = (x, y, rot, side)

    # ------------------------------------------------------------------
    def build(self, outdir):
        b = pcbnew.BOARD()
        b.SetCopperLayerCount(self.layers)
        ds = b.GetDesignSettings()
        # JLCPCB four-layer limits: 0.09 mm track, 0.2 mm from a hole to other copper
        ds.m_TrackMinWidth = mm(0.09)
        ds.m_HoleClearance = mm(0.2)
        ds.m_MinClearance = mm(0.127)
        ds.m_ViasMinSize = mm(0.45)
        ds.m_MinThroughDrill = mm(0.2)
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetTrackWidth(mm(self.rules["track"]))
        nc.SetClearance(mm(self.rules["clearance"]))
        nc.SetViaDiameter(mm(self.rules["via"][0]))
        nc.SetViaDrill(mm(self.rules["via"][1]))

        # net classes: a width, or (width, clearance) for high-voltage nets
        classes = {}
        for net, spec in self.wide.items():
            classes.setdefault(spec if isinstance(spec, tuple) else (spec, None), []).append(net)
        for (width, clr), members in sorted(classes.items(), key=str):
            name = f"W{int(round(width * 1000))}" + (f"C{int(round(clr * 1000))}" if clr else "")
            wc = pcbnew.NETCLASS(name)
            wc.SetTrackWidth(mm(width))
            wc.SetClearance(mm(clr or self.rules["clearance"]))
            wc.SetViaDiameter(mm(self.wide_via[0]))
            wc.SetViaDrill(mm(self.wide_via[1]))
            ds.m_NetSettings.SetNetclass(name, wc)
            for net in members:
                ds.m_NetSettings.SetNetclassPatternAssignment(net, name)

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
        self._poured = set()
        for name in self.planes:
            self._zone(b, b.GetLayerID(name))

        # keep tracks and vias off the board edge
        e = 0.8
        for x0, y0, x1, y1 in [(0, 0, self.w, e), (0, self.h - e, self.w, self.h),
                               (0, 0, e, self.h), (self.w - e, 0, self.w, self.h)]:
            k = pcbnew.ZONE(b)
            k.SetIsRuleArea(True)
            k.SetDoNotAllowTracks(True)
            k.SetDoNotAllowVias(True)
            k.SetDoNotAllowZoneFills(False)
            k.SetDoNotAllowPads(False)
            k.SetDoNotAllowFootprints(False)
            k.SetLayerSet(pcbnew.LSET.AllCuMask())
            o = k.Outline()
            o.NewOutline()
            for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
                o.Append(mm(x), mm(y))
            b.Add(k)

        os.makedirs(outdir, exist_ok=True)
        self.board = b
        self.path = os.path.join(outdir, self.sch.name + ".kicad_pcb")
        pcbnew.SaveBoard(self.path, b)
        return self.path

    def _zone(self, b, layer):
        self._poured.add(layer)
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(self._gnd)
        z.SetLocalClearance(mm(self.zone_clearance))
        z.SetMinThickness(mm(0.2))
        # solid connections: thermal spokes starve the small ground pads
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        o = z.Outline()
        o.NewOutline()
        for x, y in self._pts:
            o.Append(mm(x), mm(y))
        b.Add(z)

    def top_pour(self):
        """Ground on every copper layer that was left free for routing."""
        layers = [pcbnew.F_Cu, pcbnew.B_Cu]
        if self.layers == 4:
            layers += [pcbnew.In1_Cu, pcbnew.In2_Cu]
        for layer in layers:
            if layer not in self._poured:
                self._zone(self.board, layer)
        pcbnew.SaveBoard(self.path, self.board)

    def stitch(self, pitch=4.0, margin=0.35):
        """Ground vias on a grid wherever nothing is in the way.

        They tie the outer pours to the planes.  Without them a patch of top
        pour fenced in by tracks is left floating, and with it any ground pad
        whose only connection was that pour (the top-side pads of an
        edge-mount connector, for one).
        """
        b = self.board
        dia, drill = self.rules["via"]
        r = dia / 2
        M = pcbnew.ToMM
        segs, discs, boxes = [], [], []
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                discs.append((M(p.x), M(p.y), M(t.GetWidth(pcbnew.F_Cu)) / 2))
            else:
                a, e = t.GetStart(), t.GetEnd()
                segs.append((M(a.x), M(a.y), M(e.x), M(e.y), M(t.GetWidth()) / 2))
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                boxes.append((M(bb.GetLeft()), M(bb.GetTop()), M(bb.GetRight()), M(bb.GetBottom())))
            cy = fp.GetCourtyard(pcbnew.F_CrtYd if not fp.IsFlipped() else pcbnew.B_CrtYd)
            if cy.OutlineCount() and fp.GetReference().startswith("H"):
                bb = cy.BBox()
                boxes.append((M(bb.GetLeft()), M(bb.GetTop()), M(bb.GetRight()), M(bb.GetBottom())))

        def free(x, y):
            g = r + margin
            for x0, y0, x1, y1 in boxes:
                if x0 - g < x < x1 + g and y0 - g < y < y1 + g:
                    return False
            for cx, cy_, cr in discs:
                if (x - cx) ** 2 + (y - cy_) ** 2 < (cr + g) ** 2:
                    return False
            for x0, y0, x1, y1, hw in segs:
                dx, dy = x1 - x0, y1 - y0
                L2 = dx * dx + dy * dy
                t = 0 if L2 == 0 else max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / L2))
                if (x - x0 - t * dx) ** 2 + (y - y0 - t * dy) ** 2 < (hw + g) ** 2:
                    return False
            return True

        n = 0
        y = 2.0
        while y < self.h - 1.9:
            x = 2.0
            while x < self.w - 1.9:
                if free(x, y):
                    v = pcbnew.PCB_VIA(b)
                    v.SetPosition(P(x, y))
                    v.SetWidth(pcbnew.F_Cu, mm(dia))
                    v.SetDrill(mm(drill))
                    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    v.SetNet(self._gnd)
                    b.Add(v)
                    n += 1
                x += pitch
            y += pitch
        return n

    def sma(self, ref, side, pos):
        """Edge-launch SMA: the footprint's board edge is 1.54 mm from its
        origin and the connector body points along +x."""
        self.edge_refs.add(ref)
        if side == "L":
            self.place(ref, 1.54, pos, 180)
        elif side == "R":
            self.place(ref, self.w - 1.54, pos, 0)
        elif side == "T":
            self.place(ref, pos, 1.54, 270)
        else:
            self.place(ref, pos, self.h - 1.54, 90)

    def route(self, workdir, passes=20):
        os.makedirs(workdir, exist_ok=True)
        dsn = os.path.join(workdir, self.sch.name + ".dsn")
        ses = os.path.join(workdir, self.sch.name + ".ses")
        for f in (dsn, ses):
            if os.path.exists(f):
                os.remove(f)
        if not pcbnew.ExportSpecctraDSN(self.board, dsn):
            raise RuntimeError("DSN export failed")
        # A ground plane is not a routing layer.  The router does not see the
        # pour, so unless the layer is switched off it runs tracks through
        # the plane and cuts it up.  Vias still pass through and connect.
        rules = os.path.join(workdir, self.sch.name + ".rules")
        names = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"] if self.layers == 4 else ["F.Cu", "B.Cu"]
        with open(rules, "w") as f:
            f.write(f"(rules PCB {self.sch.name}\n  (snap_angle fortyfive_degree)\n"
                    "  (autoroute_settings\n    (fanout off)\n    (autoroute on)\n"
                    "    (postroute on)\n    (vias on)\n    (via_costs 50)\n"
                    "    (plane_via_costs 5)\n    (start_ripup_costs 100)\n"
                    "    (start_pass_no 1)\n")
            for i, name in enumerate(names):
                active = "off" if name in self.planes else "on"
                way = "horizontal" if i % 2 == 0 else "vertical"
                f.write(f"    (layer_rule {name}\n      (active {active})\n"
                        f"      (preferred_direction {way})\n"
                        "      (preferred_direction_trace_costs 1.0)\n"
                        "      (against_preferred_direction_trace_costs 2.0)\n    )\n")
            f.write("  )\n)\n")
        # The router needs no network; give it none.
        cmd = [FREEROUTING, "-de", dsn, "-dr", rules, "-do", ses, "-mp", str(passes), "-mt", "8",
               "--gui.enabled=false"]
        if subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0:
            cmd = ["unshare", "-rn"] + cmd
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        self.route_log = "\n".join(l[25:] for l in r.stdout.splitlines() if "DEBUG" not in l)[-1500:]
        if not os.path.exists(ses):
            raise RuntimeError("autorouter produced nothing:\n" + self.route_log)
        if not pcbnew.ImportSpecctraSES(self.board, ses):
            raise RuntimeError("SES import failed")
        self.stitched = self.stitch(margin=max(0.35, self.zone_clearance + 0.3))
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

    IGNORED = ("lib_footprint_issues", "silk_overlap", "silk_over_copper", "silk_edge_clearance")

    def run(self, outdir, workdir, route=False, png=True):
        """Build, optionally route, check and render; print a short report."""
        self.build(outdir)
        if self.unmapped:
            print("pads with no schematic pin:", " ".join(self.unmapped))
        if route:
            self.route(workdir)
        else:
            self.top_pour()
        r = self.drc(workdir)
        def expected(v):
            # an edge-mount connector's pads are meant to reach the outline
            return v[1] == "copper_edge_clearance" and any(
                f" of {ref} " in v[3] + " " for ref in self.edge_refs)
        real = [v for v in r["violations"] if v[1] not in self.IGNORED and not expected(v)]
        print(f"{self.sch.name}: {len(real)} rule violations, {len(r['unconnected'])} unconnected"
              + ("" if route else " (not routed)"))
        for v in real[:12]:
            print("   ", v[1], "|", v[3][:110])
        for u in r["unconnected"][:6] if route else []:
            print("    unconnected |", u[:110])
        svg = self.svg(workdir, "F.Cu,F.SilkS,F.CrtYd,Edge.Cuts", "top")
        if png:
            out = os.path.join(outdir, self.sch.name + "-top.png")
            subprocess.run(["magick", "-density", "380", "-background", "white", svg, "-flatten",
                            "-resize", "1600x", out], capture_output=True)
        return not real and (not route or not r["unconnected"])
