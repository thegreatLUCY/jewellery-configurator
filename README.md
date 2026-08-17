# Jewellery Configurator

A browser-based 3D jewellery configurator: pick a piece (ring or bracelet),
stone shape, metal, and stone colour, and see it rendered live with real
physically-based materials — volumetric gem colour, dispersion ("fire"),
studio lighting, and a baked micro-roughness gold finish.

Built with [`<model-viewer>`](https://modelviewer.dev/) (glTF/GLB) — no
build step, no server-side code. Pure static HTML/CSS/JS.

## Run it

Any static file server works, e.g.:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080/`.

(Opening `index.html` directly via `file://` will hit CORS restrictions on
loading the `.glb`/`.hdr` assets — serve it instead.)

## What's in each file

- `index.html` — the app: UI, state, and the model-viewer wiring (variant
  switching, camera framing, zoom preservation across piece/shape switches).
- `ring_round.glb`, `ring_princess.glb`, `bracelet.glb` — the 3D assets.
  Each is a single glTF file carrying **all** metal × stone-colour
  combinations as [`KHR_materials_variants`](https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_materials_variants),
  so switching colour/metal is instant with no network request — only
  switching piece or stone *shape* re-fetches a model.
- `studio.hdr` — a custom-generated neutral studio lighting environment
  (script in `pipeline/`). Off-the-shelf HDRIs either cast an unwanted colour
  tint or were too soft to put real specular highlights on the metal; this
  one is a small set of bright panels against a dark surround, tuned to give
  jewellery-photography-style contrast without tinting anything.

## `pipeline/` — how the assets were built

These are the Blender (`bpy`) scripts used to go from raw AI-generated
3D scans to the shipped assets. They are **reference material, not a
one-command build** — they expect the original source meshes (not included
here) and were run interactively against an evolving `.blend` file, so
treat them as documentation of the process rather than a runnable pipeline:

- `build_diamond2.py` — procedural round-brilliant-cut gem geometry (real
  facet structure: table, star/kite crown facets, lower-girdle + main
  pavilion facets), replacing the AI-generated stone.
- `build_princess.py` — same idea for a princess cut, plus exporting
  per-colour variants for that shape.
- `build_gold.py` — UV-unwraps the band and bakes a micro-roughness texture
  (the source mesh had none, so metal roughness was previously a single flat
  value across the whole surface).
- `build_optimized.py` — mesh cleanup/decimation pipeline: the raw AI export
  was ~530k triangles for a smooth band; this gets it down to a size
  appropriate for the web with negligible visual loss (smooth-then-decimate,
  not naive decimation, to avoid a "hammered metal" artifact).
- `build_bracelet.py` — same pipeline applied to the bracelet asset.
- `patch_variants.py` — post-processes an exported `.glb` to add the
  `KHR_materials_variants` metal/stone combinations directly in glTF JSON
  (Blender's exporter doesn't do this itself), including realistic
  per-stone-colour volumetric absorption/dispersion tuned to each colour.
- `make_studio_hdr.py` — generates `studio.hdr` from scratch (no external
  HDRI dependency).

## Notes

- Requires a browser with WebGL2. Tested via `@google/model-viewer` 4.3.1.
- No analytics, no backend, no build tooling — it's intentionally just static
  files.
