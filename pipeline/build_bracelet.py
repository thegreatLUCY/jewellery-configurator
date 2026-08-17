"""
Build the Topaz bangle into the same optimised form as the rings.

The export is the AI chunking pattern again: 27 fragments of the metal and 27
fragments of the single stone, each fragment spanning the whole part. So they
merge into exactly two objects -- metal and gem -- like the ring did.

Names are deliberately aligned with the ring build (Band / Diamond, materials
Gold / Diamond_Base) so one downstream patcher handles every asset.
"""
import bpy, os, mathutils

src = "/Users/robeirtoma/Downloads/Toapz Braclet (1)"
out_dir = "/private/tmp/claude-501/-Users-robeirtoma/218035ca-7e83-4096-a998-68e093b899ac/scratchpad/ring_mvp"

# NOTE: deliberately different treatment from the ring.
# The ring's shank is chunky, so Smooth+0.08 was free. This bangle is a long
# THIN band (~0.058 long, ~0.011 thick) with a small clasp, and both operations
# punish that: Smooth pulls the thin cross-section toward its own centreline
# (denting the band and flattening the prongs into straps), and 0.05 leaves too
# few triangles to hold the silhouette or the clasp links.
# Verified by render sweep: no smoothing + 0.15 is near-indistinguishable from
# the 712k original, while Smooth+0.05 visibly wrecked it.
DECIMATE_RATIO = 0.15
SMOOTH_ITERS = 0
GOLD_ROUGHNESS = 0.16     # matches the ring build; final values come from the patcher

bpy.ops.wm.read_factory_settings(use_empty=True)
for i in range(54):
    bpy.ops.wm.obj_import(filepath=os.path.join(src, f"model_{i}.obj"))

mesh_objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
metal_parts = [o for o in mesh_objs if len(o.data.vertices) > 5000]
stone_parts = [o for o in mesh_objs if len(o.data.vertices) <= 5000]
print(f"metal parts={len(metal_parts)} stone parts={len(stone_parts)}")


def join(parts, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    obj.data.name = name
    obj.data.materials.clear()
    return obj


band = join(metal_parts, "Band")
gem = join(stone_parts, "DiamondGem_Topaz")

# ---- metal: relax AI noise, then decimate, then smooth-shade ----
bpy.ops.object.select_all(action='DESELECT')
band.select_set(True)
bpy.context.view_layer.objects.active = band

if SMOOTH_ITERS:
    sm = band.modifiers.new(name="Smooth", type='SMOOTH')
    sm.iterations = SMOOTH_ITERS
    sm.factor = 0.5
    bpy.ops.object.modifier_apply(modifier=sm.name)

dec = band.modifiers.new(name="Decimate", type='DECIMATE')
dec.decimate_type = 'COLLAPSE'
dec.ratio = DECIMATE_RATIO
bpy.ops.object.modifier_apply(modifier=dec.name)
bpy.ops.object.shade_smooth()

# ---- gem: keep full density and flat-shade so facet edges stay crisp ----
bpy.ops.object.select_all(action='DESELECT')
gem.select_set(True)
bpy.context.view_layer.objects.active = gem
bpy.ops.object.shade_flat()

gold = bpy.data.materials.new("Gold")
gold.use_nodes = True
gb = gold.node_tree.nodes["Principled BSDF"]
gb.inputs["Base Color"].default_value = (1.0, 0.766, 0.336, 1.0)
gb.inputs["Metallic"].default_value = 1.0
gb.inputs["Roughness"].default_value = GOLD_ROUGHNESS
band.data.materials.append(gold)

gemmat = bpy.data.materials.new("Diamond_Base")
gemmat.use_nodes = True
db = gemmat.node_tree.nodes["Principled BSDF"]
db.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
db.inputs["Metallic"].default_value = 0.0
db.inputs["Roughness"].default_value = 0.015
db.inputs["IOR"].default_value = 2.417
tkey = "Transmission Weight" if "Transmission Weight" in db.inputs else "Transmission"
db.inputs[tkey].default_value = 1.0
gem.data.materials.append(gemmat)

for o in (band, gem):
    while o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers[0])

print(f"metal tris={len(band.data.polygons):,}  gem tris={len(gem.data.polygons):,}")

# gem bbox -> the patcher scales volume absorption to the asset's units
mn = [1e9]*3; mx = [-1e9]*3
for c in gem.bound_box:
    w = gem.matrix_world @ mathutils.Vector(c)
    for i in range(3):
        mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
print("GEMSIZE", [round(mx[i]-mn[i], 5) for i in range(3)])

# ---- render QA ----
mins=[1e9]*3; maxs=[-1e9]*3
for o in (band, gem):
    for c in o.bound_box:
        w = o.matrix_world @ mathutils.Vector(c)
        for i in range(3):
            mins[i]=min(mins[i],w[i]); maxs[i]=max(maxs[i],w[i])
center = mathutils.Vector([(mins[i]+maxs[i])/2 for i in range(3)])
size = max(maxs[i]-mins[i] for i in range(3)); dist = size*2.2

w = bpy.data.worlds.new("W"); bpy.context.scene.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.06,0.06,0.07,1)
bpy.ops.object.light_add(type='SUN', location=center+mathutils.Vector((dist,-dist,dist)))
bpy.context.object.data.energy = 4
bpy.ops.object.light_add(type='SUN', location=center+mathutils.Vector((-dist,dist,dist*0.5)))
bpy.context.object.data.energy = 2

cam_pos = center + mathutils.Vector((dist*0.5, -dist*0.9, dist*0.55))
bpy.ops.object.camera_add(location=cam_pos)
cam = bpy.context.object
cam.rotation_euler = (center-cam_pos).to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera = cam

sc = bpy.context.scene
for eng in ('BLENDER_EEVEE_NEXT','BLENDER_EEVEE'):
    try: sc.render.engine = eng; break
    except TypeError: continue
sc.render.resolution_x = 1200; sc.render.resolution_y = 900
sc.render.filepath = os.path.join(out_dir, "bracelet_built.png")
bpy.ops.render.render(write_still=True)

glb = os.path.join(out_dir, "bracelet.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=False,
                          export_apply=True,
                          export_draco_mesh_compression_enable=True,
                          export_draco_mesh_compression_level=6)
print(f"RESULT bracelet size={os.path.getsize(glb)/1e6:.2f}MB")
print("BUILD DONE")
