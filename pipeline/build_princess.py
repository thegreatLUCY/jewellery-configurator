import bpy, bmesh, math, os
from mathutils import Vector

out_dir = "/private/tmp/claude-501/-Users-robeirtoma/218035ca-7e83-4096-a998-68e093b899ac/scratchpad/ring_mvp"
blend_path = os.path.join(out_dir, "ring_final.blend")

bpy.ops.wm.open_mainfile(filepath=blend_path)
diamond_obj = bpy.data.objects["Diamond"]

bb = diamond_obj.bound_box
xs = [c[0] for c in bb]; ys = [c[1] for c in bb]; zs = [c[2] for c in bb]
old_min = Vector((min(xs), min(ys), min(zs)))
old_max = Vector((max(xs), max(ys), max(zs)))
old_center = (old_min + old_max) / 2
old_size = old_max - old_min
half_w_target = max(old_size.x, old_size.z) / 2   # fit to same footprint as the round gem
height_target = old_size.y

# --- princess cut: square table/girdle, faceted crown, pointed pavilion ---
# (Simplified vs. a real ~50-facet princess cut, which also chamfers the girdle
#  corners — this keeps the square outline + step-style faceting that reads as
#  "princess cut" without that extra corner-chamfer complexity.)
hw = 1.0                     # half-width of girdle (unit), scaled to target after
table_hw = 0.62 * hw
crown_h = 0.42
girdle_half = 0.01
mid_hw = 0.34 * hw            # pavilion mid-square, between girdle and culet
mid_depth = 0.55
culet_depth = 1.05

bm = bmesh.new()

def sq(half, y):
    # 4 corners of a square, CCW, at height y
    return [
        bm.verts.new((half, y, half)),
        bm.verts.new((-half, y, half)),
        bm.verts.new((-half, y, -half)),
        bm.verts.new((half, y, -half)),
    ]

def mid_ring(inner_half, outer_half, y):
    # 8 points: 4 corners (outer) + 4 edge midpoints (slightly inset), alternating
    pts = []
    corners = [(outer_half, outer_half), (-outer_half, outer_half), (-outer_half, -outer_half), (outer_half, -outer_half)]
    for i in range(4):
        cx, cz = corners[i]
        nx, nz = corners[(i + 1) % 4]
        pts.append(bm.verts.new((cx, y, cz)))
        pts.append(bm.verts.new(((cx + nx) / 2, y, (cz + nz) / 2)))
    return pts

T = sq(table_hw, crown_h)                 # 4 table corners
G = mid_ring(0, hw, girdle_half)          # 8 girdle points (top side)
Gp = mid_ring(0, hw, -girdle_half)        # 8 girdle points (pavilion side)
M = sq(mid_hw, -mid_depth)                # 4 pavilion mid-square corners
culet = bm.verts.new((0, -culet_depth, 0))

bm.verts.ensure_lookup_table()

# table
bm.faces.new(T)

# crown: each table edge fans to 2 girdle points (corner + midpoint) -> 8 triangles
for i in range(4):
    t0, t1 = T[i], T[(i + 1) % 4]
    g_corner = G[2 * i]
    g_mid = G[2 * i + 1]
    g_next_corner = G[(2 * i + 2) % 8]
    bm.faces.new((t0, g_corner, g_mid))
    bm.faces.new((t0, g_mid, t1))
    bm.faces.new((t1, g_mid, g_next_corner))

# girdle band (8 quads)
for i in range(8):
    a0, a1 = G[i], G[(i + 1) % 8]
    b0, b1 = Gp[i], Gp[(i + 1) % 8]
    bm.faces.new((a0, a1, b1, b0))

# pavilion stage 1: girdle(8) -> mid square(4), fan (8 triangles)
for i in range(4):
    m0 = M[i]
    g_corner = Gp[2 * i]
    g_mid = Gp[2 * i - 1] if i > 0 else Gp[7]
    g_mid2 = Gp[2 * i + 1]
    bm.faces.new((m0, g_mid, g_corner))
    bm.faces.new((m0, g_corner, g_mid2))

# pavilion stage 2: mid square(4) -> culet (4 triangles)
for i in range(4):
    m0, m1 = M[i], M[(i + 1) % 4]
    bm.faces.new((m0, m1, culet))

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

new_mesh = bpy.data.meshes.new("DiamondGem_Princess")
bm.to_mesh(new_mesh)
bm.free()

raw_height = crown_h + culet_depth
# fit by CORNER distance (hw * sqrt(2)), not edge half-width — the girdle's
# corners are what needs to stay within the prongs' aperture, and a square's
# corner reaches sqrt(2) further than its edge midpoint.
scale_xz = half_w_target / (hw * math.sqrt(2))
scale_y = height_target / raw_height
for v in new_mesh.vertices:
    v.co.x *= scale_xz
    v.co.z *= scale_xz
    v.co.y *= scale_y
ys_new = [v.co.y for v in new_mesh.vertices]
shift_y = old_center.y - (min(ys_new) + max(ys_new)) / 2
for v in new_mesh.vertices:
    v.co.x += old_center.x
    v.co.y += shift_y
    v.co.z += old_center.z

old_mesh = diamond_obj.data
diamond_mat = old_mesh.materials[0] if old_mesh.materials else bpy.data.materials.get("Diamond_Black")
diamond_obj.data = new_mesh
new_mesh.materials.append(diamond_mat)
if old_mesh.users == 0:
    bpy.data.meshes.remove(old_mesh)

bpy.context.view_layer.objects.active = diamond_obj
bpy.ops.object.select_all(action='DESELECT')
diamond_obj.select_set(True)
bpy.ops.object.shade_flat()

scene = bpy.context.scene
scene.render.filepath = os.path.join(out_dir, "render_princess.png")
bpy.ops.render.render(write_still=True)

# --- export the same 4 tuned color variants for this shape ---
bsdf = diamond_mat.node_tree.nodes.get("Principled BSDF")
def get_transmission_input():
    return bsdf.inputs["Transmission Weight"] if "Transmission Weight" in bsdf.inputs else bsdf.inputs["Transmission"]

variants = {
    "black":     ((0.03, 0.03, 0.032, 1.0), 0.35, 0.035, 2.417),
    "colorless": ((0.98, 0.99, 1.00, 1.0),  0.92, 0.010, 2.417),
    "champagne": ((0.62, 0.38, 0.10, 1.0),  0.62, 0.015, 2.417),
    "pink":      ((0.88, 0.12, 0.42, 1.0),  0.60, 0.015, 2.417),
    "emerald":   ((0.04, 0.42, 0.20, 1.0),  0.50, 0.015, 2.417),
}
for name, (col, trans, rough, ior) in variants.items():
    bsdf.inputs["Base Color"].default_value = col
    get_transmission_input().default_value = trans
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["IOR"].default_value = ior
    glb_path = os.path.join(out_dir, f"ring_princess_{name}.glb")
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=False, export_apply=True)
    print("exported", glb_path)

print("DONE facets:", len(new_mesh.polygons))
