#!/usr/bin/env python3
"""
Bake metal x stone options into every asset as KHR_materials_variants.

Two things this guarantees that per-asset authoring cannot:

1. The metals are defined ONCE here and written identically into every asset,
   so yellow/white gold match 100% across ring and bracelet. If the values
   lived in each Blender build script they would drift.

2. Volume absorption is scaled to each asset's units. Gem colour is
   Beer-Lambert absorption over distance travelled through the stone, so
   thicknessFactor/attenuationDistance are LENGTHS. The ring is modelled at
   ~5 units across the gem, the bangle at ~0.014 -- reusing raw numbers would
   make the bangle's stone read as flat colour. So values are authored against
   a reference gem width and rescaled per asset from its actual gem bbox.

Variants are named "<Metal>_<Stone>", e.g. "White_Emerald".
"""
import struct, json, os, sys

REFERENCE_GEM_WIDTH = 5.0     # units the gem specs below were tuned against

METALS = {
    "Yellow": {"baseColorFactor": [1.0, 0.766, 0.336, 1.0], "metallicFactor": 1.0, "roughnessFactor": 0.16},
    # Rhodium-plated white gold: bright and near-mirror, faintly WARM rather than
    # cold chrome. Tested live -- the previous 0.913/r0.11 read flat and chalky
    # (pewter-like), and physically-accurate rhodium (~0.80) went too dark against
    # this dark backdrop, where a mirror has little bright to reflect.
    "White":  {"baseColorFactor": [0.962, 0.957, 0.946, 1.0], "metallicFactor": 1.0, "roughnessFactor": 0.06},
}

#          baseColor(near-white when transmissive)  transm  thick  attenuationColor      attenDist  dispersion
GEMS = {
    # trailing value is roughness. A perfectly mirror table (0.015) blew out
    # under the studio panels; 0.035-0.05 still reads polished but spreads the
    # highlight instead of clipping. Black gets the most: real black diamonds are
    # opaque and comparatively lustrous-not-mirror, and it must stay BLACK.
    # trailing fields are roughness and SPECULAR strength.
    # Blender exported specularColorFactor [2,2,2] on the template (its "Specular
    # IOR Level" 1.0 maps to 2.0), which doubled every gem's reflection -- the
    # main reason a black stone's flat table blew out to white. We now set
    # specular explicitly instead of inheriting it.
    # Black is opaque by nature: no transmission, duller finish, damped specular,
    # so it reads BLACK instead of mirroring the softboxes.
    "Black":     ((0.015, 0.015, 0.017, 1.0), 0.00, 2.6, (0.005, 0.005, 0.006), 0.15, 0.010, 0.300, 0.22),
    "Colorless": ((1.00, 1.00, 1.00,  1.0), 1.00, 2.6, (0.96, 0.97, 1.00),  18.00, 0.044, 0.030, 1.00),
    "Champagne": ((1.00, 1.00, 1.00,  1.0), 1.00, 2.6, (0.78, 0.44, 0.11),   1.60, 0.035, 0.040, 1.00),
    "Pink":      ((1.00, 1.00, 1.00,  1.0), 1.00, 2.6, (0.95, 0.10, 0.38),   1.45, 0.030, 0.040, 1.00),
    "Emerald":   ((1.00, 1.00, 1.00,  1.0), 1.00, 2.6, (0.05, 0.62, 0.26),   1.15, 0.022, 0.040, 1.00),
}

ASSETS = ["ring_round.glb", "ring_princess.glb", "bracelet.glb"]

EXTS = ["KHR_materials_transmission", "KHR_materials_volume",
        "KHR_materials_dispersion", "KHR_materials_variants"]

JSON_CHUNK = 0x4E4F534A


def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, _, total = struct.unpack("<4sII", data[:12])
    if magic != b"glTF":
        raise ValueError(f"{path}: not a GLB")
    chunks, off = [], 12
    while off < total:
        clen, ctype = struct.unpack("<II", data[off:off + 8])
        chunks.append([ctype, data[off + 8: off + 8 + clen]])
        off += 8 + clen
    return chunks


def write_glb(path, chunks):
    body = b""
    for ctype, cdata in chunks:
        pad = (4 - (len(cdata) % 4)) % 4
        if pad:
            cdata += (b" " * pad if ctype == JSON_CHUNK else b"\x00" * pad)
        body += struct.pack("<II", len(cdata), ctype) + cdata
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)


def gem_scale(g, gem_prims):
    """Width of the gem from its POSITION accessor bbox, relative to reference."""
    widths = []
    for mesh_i, prim_i in gem_prims:
        prim = g["meshes"][mesh_i]["primitives"][prim_i]
        acc = g["accessors"][prim["attributes"]["POSITION"]]
        if "min" in acc and "max" in acc:
            widths.append(max(acc["max"][i] - acc["min"][i] for i in range(3)))
    if not widths:
        return 1.0, None
    w = max(widths)
    return w / REFERENCE_GEM_WIDTH, w


def build_gem_material(template, name, spec, scale):
    base_col, transm, thick, atten_col, atten_dist, dispersion, rough, specular = spec
    m = json.loads(json.dumps(template))
    m["name"] = f"Diamond_{name}"
    pbr = m.setdefault("pbrMetallicRoughness", {})
    pbr["baseColorFactor"] = list(base_col)
    pbr["metallicFactor"] = 0.0
    pbr["roughnessFactor"] = rough
    ext = m.setdefault("extensions", {})
    ext["KHR_materials_transmission"] = {"transmissionFactor": transm}
    ext["KHR_materials_volume"] = {
        "thicknessFactor": thick * scale,          # lengths -> scale per asset
        "attenuationColor": list(atten_col),
        "attenuationDistance": atten_dist * scale,
    }
    ext["KHR_materials_dispersion"] = {"dispersion": dispersion}
    ext["KHR_materials_ior"] = {"ior": 2.417}
    # overwrite, never inherit: the template carries a non-physical 2x boost
    ext["KHR_materials_specular"] = {
        "specularFactor": specular,
        "specularColorFactor": [1.0, 1.0, 1.0],
    }
    return m


def build_metal_material(template, name, spec):
    m = json.loads(json.dumps(template))
    m["name"] = f"Gold_{name}"
    m["pbrMetallicRoughness"] = dict(spec)
    m.pop("extensions", None)                      # plain metal, no transmission
    return m


def patch(path):
    chunks = read_glb(path)
    ji = next(i for i, c in enumerate(chunks) if c[0] == JSON_CHUNK)
    g = json.loads(chunks[ji][1].decode("utf-8"))

    mats = g["materials"]
    gem_i = next(i for i, m in enumerate(mats) if m.get("name", "").startswith("Diamond"))
    metal_i = next(i for i, m in enumerate(mats) if m.get("name", "").startswith("Gold"))

    # Idempotence: a previous run leaves Gold_<metal>/Diamond_<stone> behind. If we
    # only dropped the two templates, re-running would keep the OLD generated
    # materials as "other" materials and append a fresh set beside them, growing
    # the list every run. So treat anything matching our generated names as ours
    # to replace, not as foreign material to preserve.
    generated = {f"Gold_{m}" for m in METALS} | {f"Diamond_{s}" for s in GEMS}

    # Locate primitives by the NAME of the material they reference, not its index.
    # Index matching breaks on an already-patched file, where primitives point at
    # generated materials rather than the template we picked.
    def role(prim):
        idx = prim.get("material")
        if idx is None:
            return None
        nm = mats[idx].get("name", "")
        if nm.startswith("Diamond"):
            return "gem"
        if nm.startswith("Gold"):
            return "metal"
        return None

    gem_prims, metal_prims = [], []
    for mi, mesh in enumerate(g["meshes"]):
        for pi, prim in enumerate(mesh["primitives"]):
            r = role(prim)
            if r == "gem":
                gem_prims.append((mi, pi))
            elif r == "metal":
                metal_prims.append((mi, pi))
    if not gem_prims or not metal_prims:
        raise ValueError(f"{path}: gem_prims={len(gem_prims)} metal_prims={len(metal_prims)}")

    scale, gw = gem_scale(g, gem_prims)

    metal_names = list(METALS)
    gem_names = list(GEMS)
    G = len(gem_names)

    new_metals = [build_metal_material(mats[metal_i], n, METALS[n]) for n in metal_names]
    new_gems = [build_gem_material(mats[gem_i], n, GEMS[n], scale) for n in gem_names]

    keep, remap = [], {}
    for i, m in enumerate(mats):
        if i in (gem_i, metal_i) or m.get("name") in generated:
            continue
        remap[i] = len(keep)
        keep.append(m)
    metal_base = len(keep)
    gem_base = metal_base + len(new_metals)
    g["materials"] = keep + new_metals + new_gems

    variants = [f"{m}_{s}" for m in metal_names for s in gem_names]
    g.setdefault("extensions", {})["KHR_materials_variants"] = {
        "variants": [{"name": v} for v in variants]
    }

    # any primitive that is neither gem nor metal must follow the reindexed list
    gem_set, metal_set = set(gem_prims), set(metal_prims)
    for mi, mesh in enumerate(g["meshes"]):
        for pi, prim in enumerate(mesh["primitives"]):
            if (mi, pi) in gem_set or (mi, pi) in metal_set:
                continue
            if "material" in prim and prim["material"] in remap:
                prim["material"] = remap[prim["material"]]

    for mi, pi in metal_prims:
        prim = g["meshes"][mi]["primitives"][pi]
        prim["material"] = metal_base
        prim.setdefault("extensions", {})["KHR_materials_variants"] = {
            "mappings": [
                {"material": metal_base + m, "variants": [m * G + s for s in range(G)]}
                for m in range(len(metal_names))
            ]
        }

    for mi, pi in gem_prims:
        prim = g["meshes"][mi]["primitives"][pi]
        prim["material"] = gem_base
        prim.setdefault("extensions", {})["KHR_materials_variants"] = {
            "mappings": [
                {"material": gem_base + s, "variants": [m * G + s for m in range(len(metal_names))]}
                for s in range(G)
            ]
        }

    used = g.setdefault("extensionsUsed", [])
    for e in EXTS:
        if e not in used:
            used.append(e)

    chunks[ji][1] = json.dumps(g, separators=(",", ":")).encode("utf-8")
    write_glb(path, chunks)
    return len(variants), scale, gw


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    for fn in ASSETS:
        p = os.path.join(target, fn)
        if not os.path.exists(p):
            print("SKIP (missing):", fn); continue
        n, scale, gw = patch(p)
        print(f"patched {fn:20s} {os.path.getsize(p)/1e6:5.2f}MB  variants={n}  "
              f"gem_width={gw:.4f}  volume_scale={scale:.5f}")
    print(f"\nvariants = {list(METALS)} x {list(GEMS)}")
    print("DONE")


if __name__ == "__main__":
    main()
