"""Write KiCad schematics from a Python description of parts and nets.

Each board is a script that places symbols from KiCad's own libraries and
says which net every pin is on.  A pin gets a short wire stub ending in a net
label (or a power symbol, or a no-connect flag), so connectivity is carried by
names rather than by drawn wires.  That is less pretty than a hand-drawn
sheet and much harder to get wrong: `verify()` exports the netlist with
kicad-cli and checks that KiCad's own reading of the file gives every pin the
net the script asked for.
"""
import copy
import json
import os
import re
import subprocess
import uuid

SYMDIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
G = 2.54   # placement grid, mm


class Q(str):
    """A string that is written back quoted."""


def parse(text):
    tok = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')
    stack, cur = [], []
    for m in tok.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif t[0] == '"':
            cur.append(Q(t[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            cur.append(t)
    return cur[0]


def dump(node, depth=0):
    if isinstance(node, Q):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if not isinstance(node, list):
        return str(node)
    flat = "(" + " ".join(dump(n) for n in node) + ")"
    if len(flat) < 100 or depth > 6:
        return flat
    pad = "\t" * (depth + 1)
    head = [dump(node[0])]
    i = 1
    while i < len(node) and not isinstance(node[i], list):
        head.append(dump(node[i]))
        i += 1
    body = "".join("\n" + pad + dump(n, depth + 1) for n in node[i:])
    return "(" + " ".join(head) + body + "\n" + "\t" * depth + ")"


def child(node, name):
    for n in node[1:]:
        if isinstance(n, list) and n and n[0] == name:
            return n
    return None


def children(node, name):
    return [n for n in node[1:] if isinstance(n, list) and n and n[0] == name]


_libs = {}


def _lib(name):
    if name not in _libs:
        with open(os.path.join(SYMDIR, name + ".kicad_sym")) as f:
            _libs[name] = {s[1]: s for s in children(parse(f.read()), "symbol")}
    return _libs[name]


def load_symbol(lib_id):
    """A library symbol, flattened if it extends another, named `lib_id`."""
    if lib_id in _custom:
        return copy.deepcopy(_custom[lib_id])
    lib, name = lib_id.split(":")
    sym = copy.deepcopy(_lib(lib)[name])
    ext = child(sym, "extends")
    if ext:
        base = load_symbol(lib + ":" + ext[1])
        own = {p[1]: p for p in children(sym, "property")}
        out = []
        for n in base[2:]:
            if isinstance(n, list) and n[0] == "property":
                if n[1] in own:
                    n = own.pop(n[1])
            elif isinstance(n, list) and n[0] == "symbol":
                n[1] = Q(name + n[1][len(ext[1]):])
            out.append(n)
        sym = ["symbol", Q(lib_id)] + out + list(own.values())
    sym[1] = Q(lib_id)
    return sym


_custom = {}


def define_symbol(lib_id, pins, ref="U", width=None):
    """Make a box symbol for a part KiCad's libraries do not have.

    `pins` is a list of (number, name, side, type): side is L, R, T or B and
    pins are laid out along each side in the order given, 2.54 mm apart; an
    empty name leaves a gap.  type is a KiCad electrical type (input, output,
    passive, power_in, power_out, bidirectional, ...).
    """
    name = lib_id.split(":")[1]
    side = {k: [p for p in pins if p[2] == k] for k in "LRTB"}
    rows = max(len(side["L"]), len(side["R"]), 1)
    cols = max(len(side["T"]), len(side["B"]), 1)
    longest = max([len(p[1]) for p in side["L"]] + [0]) + max([len(p[1]) for p in side["R"]] + [0])
    hw = width / 2 if width else max(5.08, 2.54 * -(-(longest * 0.9 + 4) // 5.08) * 1.0,
                                     5.08 * (cols // 2 + 1))
    hw = 2.54 * round(hw / 2.54)
    # room above and below the side pins for the names of top and bottom pins
    tb = max([len(p[1]) for p in side["T"] + side["B"]] + [0])
    hh = 2.54 * ((rows + 1) // 2 + 1 + -(-tb // 3))

    def font():
        return ["effects", ["font", ["size", 1.27, 1.27]]]

    def prop(k, v, x, y, hide=False):
        e = font()
        if hide:
            e.append(["hide", "yes"])
        return ["property", Q(k), Q(v), ["at", x, y, 0], e]

    body = ["symbol", Q(name + "_0_1"),
            ["rectangle", ["start", -hw, hh], ["end", hw, -hh],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]]
    unit = ["symbol", Q(name + "_1_1")]
    for k, lst in side.items():
        n = len(lst)
        for i, (num, pname, _, ptype) in enumerate(lst):
            if not num:
                continue
            if k in "LR":
                y = 2.54 * ((rows - 1) / 2 - i)
                y = 2.54 * round(y / 2.54 + 0.25)
                at = [-hw - 2.54, y, 0] if k == "L" else [hw + 2.54, y, 180]
            else:
                x = 5.08 * (i - n // 2) + (2.54 if n % 2 == 0 else 0)
                at = [x, hh + 2.54, 270] if k == "T" else [x, -hh - 2.54, 90]
            unit.append(["pin", ptype, "line", ["at"] + at, ["length", 2.54],
                         ["name", Q(pname), font()], ["number", Q(str(num)), font()]])
    sym = ["symbol", Q(lib_id), ["pin_names", ["offset", 1.016]], ["exclude_from_sim", "no"],
           ["in_bom", "yes"], ["on_board", "yes"],
           prop("Reference", ref, -hw, hh + 1.27), prop("Value", name, -hw, -hh - 1.27),
           prop("Footprint", "", 0, 0, True), prop("Datasheet", "~", 0, 0, True),
           prop("Description", "", 0, 0, True), body, unit]
    _custom[lib_id] = sym
    return lib_id


def symbol_pins(sym):
    """[(unit, number, name, x, y, angle, type)] for every pin."""
    pins = []
    base = sym[1].split(":")[1]
    for sub in children(sym, "symbol"):
        m = re.match(re.escape(base) + r"_(\d+)_(\d+)$", sub[1])
        unit, style = int(m.group(1)), int(m.group(2))
        if style > 1:
            continue
        for p in children(sub, "pin"):
            at = child(p, "at")
            pins.append((unit, str(child(p, "number")[1]), str(child(p, "name")[1]),
                         float(at[1]), float(at[2]), int(float(at[3])) if len(at) > 3 else 0,
                         p[1]))
    return pins


def _rot(x, y, deg):
    for _ in range((deg // 90) % 4):
        x, y = -y, x
    return x, y


def _uid():
    return Q(str(uuid.uuid4()))


def _font(size=1.27):
    return ["effects", ["font", ["size", size, size]]]


POWER_SYMBOLS = {
    "GND": "power:GND", "+5V": "power:+5V", "+3V3": "power:+3V3",
    "+1V8": "power:+1V8", "+1V0": "power:+1V0", "+12V": "power:+12V",
    "+24V": "power:+24V", "+3.3VA": "power:+3.3VA", "+5VA": "power:+5VA",
    "VBUS": "power:VBUS", "GNDA": "power:GNDA",
}


class Schematic:
    def __init__(self, name, title, paper="A3", rev="A"):
        self.name = name
        self.uuid = _uid()
        self.paper = paper
        self.title = title
        self.rev = rev
        self.lib = {}        # lib_id -> symbol node
        self.items = []      # schematic nodes
        self.want = {}       # (ref, pin number) -> net or None
        self.parts = {}      # ref -> dict
        self.npwr = 0
        self.flagged = set()

    # -- primitives ---------------------------------------------------------
    def _use(self, lib_id):
        if lib_id not in self.lib:
            self.lib[lib_id] = load_symbol(lib_id)
        return self.lib[lib_id]

    def _wire(self, x1, y1, x2, y2):
        self.items.append(["wire", ["pts", ["xy", x1, y1], ["xy", x2, y2]],
                           ["stroke", ["width", 0], ["type", "default"]], ["uuid", _uid()]])

    def _label(self, net, x, y, ang):
        just = {0: ["left", "bottom"], 180: ["right", "bottom"],
                90: ["left", "bottom"], 270: ["right", "bottom"]}[ang]
        self.items.append(["label", Q(net), ["at", x, y, ang],
                           _font() + [["justify"] + just], ["uuid", _uid()]])

    def _instance(self, lib_id, ref, value, x, y, rot, unit, props, hide_ref=False,
                  in_bom=True, on_board=True, ref_off=None, val_off=None, hide_value=False):
        sym = self._use(lib_id)
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, rot], ["unit", unit],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"],
                ["on_board", "yes" if on_board else "no"], ["dnp", "no"],
                ["uuid", _uid()]]
        # Where the reference and value go depends on the symbol's shape:
        # beside a part with pins above and below, above and below one with
        # pins left and right, and off the top-left corner of anything larger.
        pts = [_rot(p[3], p[4], rot) for p in symbol_pins(sym) if p[0] in (0, unit)]
        xs = [x + px for px, _ in pts] or [x]
        ys = [y - py for _, py in pts] or [y]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if w < 1 and h >= 1:
            rpos, vpos, just = (x + 3.81, y - 1.27), (x + 3.81, y + 1.27), "left"
        elif h < 1:
            rpos, vpos, just = (x, y - 3.81), (x, y + 3.81), None
        else:
            rpos = (min(xs) + 3.81, min(ys) - 3.81)
            vpos = (x + 3.81, max(ys) + 1.27)
            just = "left"
        if ref_off:
            rpos, just = (x + ref_off[0], y + ref_off[1]), "left"
        if val_off:
            vpos, just = (x + val_off[0], y + val_off[1]), "left"
        (rx, ry), (vx, vy) = rpos, vpos
        # KiCad turns field text with the symbol: a stored angle of 90 on a
        # quarter-turned symbol reads horizontally, and a half turn swaps
        # which way the text is justified.
        fa = 90 if rot in (90, 270) else 0
        if rot == 180 and just:
            just = {"left": "right", "right": "left"}[just]
        allp = {"Reference": ref, "Value": value, "Footprint": "", "Datasheet": "~",
                "Description": ""}
        allp.update(props)
        for k, v in allp.items():
            if k == "Reference":
                at, hide = ["at", rx, ry, fa], hide_ref
            elif k == "Value":
                at, hide = ["at", vx, vy, fa], hide_value
            else:
                at, hide = ["at", x, y, 0], True
            eff = _font()
            if k in ("Reference", "Value") and just:
                eff.append(["justify", just])
            if hide:
                eff.append(["hide", "yes"])
            node.append(["property", Q(k), Q(v), at, eff])
        for p in symbol_pins(sym):
            if p[0] in (0, unit):
                node.append(["pin", Q(p[1]), ["uuid", _uid()]])
        node.append(["instances", ["project", Q(self.name),
                    ["path", Q("/" + self.uuid), ["reference", Q(ref)], ["unit", unit]]]])
        self.items.append(node)

    def _power(self, net, x, y, stub_ang):
        lib_id = POWER_SYMBOLS[net]
        self.npwr += 1
        up = stub_ang == 90      # stub runs up the page from the pin
        down = stub_ang == 270
        rot = 180 if ((net.startswith("GND") and up) or
                      (not net.startswith("GND") and down)) else 0
        self._instance(lib_id, f"#PWR{self.npwr:03d}", net, x, y, rot, 1, {},
                       hide_ref=True, in_bom=False)

    # -- public -------------------------------------------------------------
    def add(self, lib_id, ref, value, at, nets, rot=0, unit=1, fp="", lcsc="",
            mpn="", stub=1, ref_off=None, val_off=None, hide_value=False, rest_open=False,
            **props):
        """Place a symbol at grid position `at` and connect its pins.

        `nets` maps pin number or pin name to a net name, or to None for a
        pin deliberately left open.  Every pin of the unit must be covered,
        unless `rest_open` says that the pins not named are all left open.
        """
        sym = self._use(lib_id)
        x, y = at[0] * G, at[1] * G
        p = {"Footprint": fp}
        if lcsc:
            p["LCSC"] = lcsc
        if mpn:
            p["MPN"] = mpn
        p.update({k.replace("_", " "): v for k, v in props.items()})
        self._instance(lib_id, ref, value, x, y, rot, unit, p, ref_off=ref_off,
                       val_off=val_off, hide_value=hide_value)
        self.parts.setdefault(ref, dict(lib_id=lib_id, value=value, fp=fp, lcsc=lcsc, mpn=mpn))
        used = set()
        for (u, num, name, px, py, pang, ptype) in symbol_pins(sym):
            if u not in (0, unit):
                continue
            if num in nets:
                key = num
            elif name in nets:
                key = name
            elif rest_open:
                key = None
            else:
                raise KeyError(f"{ref} ({lib_id}): pin {num} '{name}' has no net")
            used.add(key)
            net = nets[key] if key is not None else None
            self.want[(ref, num)] = net
            rx, ry = _rot(px, py, rot)
            cx, cy = round(x + rx, 4), round(y - ry, 4)
            if net is None:
                self.items.append(["no_connect", ["at", cx, cy], ["uuid", _uid()]])
                continue
            # the pin points from its end towards the body; stub goes away
            out = (pang + rot + 180) % 360
            dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[out]
            ex, ey = round(cx + dx * stub * G, 4), round(cy + dy * stub * G, 4)
            self._wire(cx, cy, ex, ey)
            if net in POWER_SYMBOLS:
                self._power(net, ex, ey, out)
            else:
                self._label(net, ex, ey, out)
        extra = set(nets) - used - {None}
        if extra:
            raise KeyError(f"{ref} ({lib_id}): no such pin(s) {sorted(extra)}")

    def flag(self, net, at):
        """Mark a net as a power source for the rule check."""
        x, y = at[0] * G, at[1] * G
        self.npwr += 1
        self._instance("power:PWR_FLAG", f"#FLG{self.npwr:03d}", "PWR_FLAG", x, y, 0, 1, {},
                       hide_ref=True, in_bom=False, hide_value=True)
        self._wire(x, y, x, y + G)
        if net in POWER_SYMBOLS:
            self._power(net, x, y + G, 270 if net.startswith("GND") else 0)
        else:
            self._label(net, x, y + G, 270)

    def text(self, s, at, size=2.0):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"],
                           ["at", at[0] * G, at[1] * G, 0],
                           ["effects", ["font", ["size", size, size]],
                            ["justify", "left", "bottom"]], ["uuid", _uid()]])

    def write(self, outdir):
        os.makedirs(outdir, exist_ok=True)
        root = ["kicad_sch", ["version", 20250114], ["generator", Q("scandev_kisch")],
                ["generator_version", Q("9.0")], ["uuid", self.uuid], ["paper", Q(self.paper)],
                ["title_block", ["title", Q(self.title)], ["rev", Q(self.rev)],
                 ["company", Q("scandev")]],
                ["lib_symbols"] + list(self.lib.values())]
        root += self.items
        root += [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]],
                 ["embedded_fonts", "no"]]
        self.path = os.path.join(outdir, self.name + ".kicad_sch")
        with open(self.path, "w") as f:
            f.write(dump(root) + "\n")
        pro = os.path.join(outdir, self.name + ".kicad_pro")
        if not os.path.exists(pro):
            with open(pro, "w") as f:
                json.dump({"meta": {"filename": self.name + ".kicad_pro", "version": 3}}, f)
        return self.path

    def verify(self, workdir):
        """Compare KiCad's netlist of the written file with what was asked."""
        os.makedirs(workdir, exist_ok=True)
        net = os.path.join(workdir, self.name + ".net")
        r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                            "-o", net, self.path], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("netlist export failed: " + r.stdout + r.stderr)
        with open(net) as f:
            tree = parse(f.read())
        got = {}
        for n in children(child(tree, "nets"), "net"):
            name = str(child(n, "name")[1]).lstrip("/")
            for node in children(n, "node"):
                got[(str(child(node, "ref")[1]), str(child(node, "pin")[1]))] = name
        bad = []
        for key, net_ in self.want.items():
            g = got.get(key)
            if net_ is None:
                if g is not None and not g.startswith("unconnected-"):
                    bad.append(f"{key[0]}.{key[1]}: meant open, KiCad has {g}")
            elif g != net_:
                bad.append(f"{key[0]}.{key[1]}: meant {net_}, KiCad has {g}")
        for key in got:
            if key not in self.want and not key[0].startswith("#"):
                bad.append(f"{key[0]}.{key[1]}: in KiCad's netlist but never placed")
        return bad

    def erc(self, workdir):
        os.makedirs(workdir, exist_ok=True)
        rpt = os.path.join(workdir, self.name + "-erc.json")
        subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all",
                        "-o", rpt, self.path], capture_output=True, text=True)
        with open(rpt) as f:
            d = json.load(f)
        out = []
        for sheet in d.get("sheets", []):
            for v in sheet.get("violations", []):
                where = "; ".join(i.get("description", "") for i in v.get("items", []))
                out.append((v.get("severity"), v.get("type"), v.get("description"), where))
        return out

    def pdf(self, outdir):
        out = os.path.join(outdir, self.name + ".pdf")
        subprocess.run(["kicad-cli", "sch", "export", "pdf", "-o", out, self.path],
                       capture_output=True, text=True)
        return out

    def bom(self):
        rows = {}
        for ref, p in sorted(self.parts.items()):
            k = (p["value"], p["fp"], p["lcsc"], p["mpn"])
            rows.setdefault(k, []).append(ref)
        return rows
