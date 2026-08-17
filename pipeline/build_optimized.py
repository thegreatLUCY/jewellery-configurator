"""
Build ONE optimised GLB per shape (not per shape x colour).

Why: the band is 99.7% of every file and is byte-identical across all colours,
so shipping 10 files duplicated it 10 times and forced a full ~18MB reload on
every colour click. Colours become KHR_materials_variants in a later patch step,
so they cost no extra download and switch instantly.

Three size levers, in order of impact:
  1. Decimate the band 532k -> ~43k tris. It is a smooth torus with prongs; the
     AI export's density bought nothing. 0.08 verified clean, 0.05 ripples.
  2. Drop the baked roughness texture for a scalar. The re-bake was what caused
     the streaking at aggressive ratios (not the triangle count), and dropping
     it also removes the UV attribute from every vertex.
  3. Draco mesh compression.
"""
import bpy, os

out_dir = "/private/tmp/claude-501/-Users-robeirtoma/218035ca-7e83-4096-a998-68e093b899ac/scratchpad/ring_mvp"
blend_path = os.path.join(out_dir, "ring_final.blend")
princess_script = os.path.join(out_dir, "build_princess.py")

# Raised from 0.08: the brighter, more mirror-like white gold reveals mesh
# noise that the duller yellow gold hid. Still ~0.5MB per shape.
DECIMATE_RATIO = 0.15
GOLD_ROUGHNESS = 0.16


def strip_and_decimate():
    band = bpy.data.objects["Band"]
    bpy.context.view_layer.objects.active = band
    bpy.ops.object.select_all(action='DESELECT')
    band.select_set(True)

    # NO Smooth modifier. It was making things worse, not better: this mesh has
    # very uneven triangle density, and Laplacian smoothing pulls each vertex
    # toward its neighbours' average, so dense regions barely move while sparse
    # regions move a lot -- carving ripples into a surface that was already
    # smooth. Verified with a 2x2 test under the studio HDRI: with smoothing the
    # shank is scratchy, without it it is clean, and clearing the OBJ's custom
    # split normals made no difference either way.

    mod = band.modifiers.new(name="Decimate", type='DECIMATE')
    mod.decimate_type = 'COLLAPSE'
    mod.ratio = DECIMATE_RATIO
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # The band was never smooth-shaded. At 532k tiny triangles flat shading still
    # reads as smooth, but after decimation every facet shows as a "hammered"
    # surface. Smooth shading interpolates the normals and hides that for free --
    # far cheaper than paying for the triangles back.
    bpy.ops.object.shade_smooth()

    gold = bpy.data.materials["Gold"]
    nt = gold.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    rough_in = bsdf.inputs["Roughness"]
    for l in [l for l in nt.links if l.to_socket == rough_in]:
        nt.links.remove(l)
    rough_in.default_value = GOLD_ROUGHNESS
    for n in [n for n in nt.nodes if n.type in ('TEX_IMAGE', 'TEX_NOISE', 'MAP_RANGE', 'TEX_COORD')]:
        nt.nodes.remove(n)

    while band.data.uv_layers:
        band.data.uv_layers.remove(band.data.uv_layers[0])

    return len(band.data.polygons)


def export(path):
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format='GLB',
        use_selection=False,
        export_apply=True,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
    )
    return os.path.getsize(path) / 1e6


# ---- round (the blend already holds the round-brilliant gem) ----
bpy.ops.wm.open_mainfile(filepath=blend_path)
tris = strip_and_decimate()
size = export(os.path.join(out_dir, "ring_round.glb"))
print(f"RESULT round    tris={tris:,} size={size:.2f}MB")

# ---- princess: rebuild its gem, then apply the same optimisation ----
# build_princess.py swaps the gem mesh in and exports its own colour variants;
# re-running its geometry section here keeps a single source of truth for the cut.
bpy.ops.wm.open_mainfile(filepath=blend_path)
src = open(princess_script).read()
geom_only = src.split("# --- export the same 4 tuned color variants")[0]
geom_only = geom_only.replace('bpy.ops.wm.open_mainfile(filepath=blend_path)', '')
exec(compile(geom_only, princess_script, 'exec'), {'__name__': 'princess_geom'})

tris = strip_and_decimate()
size = export(os.path.join(out_dir, "ring_princess.glb"))
print(f"RESULT princess tris={tris:,} size={size:.2f}MB")
print("BUILD DONE")
