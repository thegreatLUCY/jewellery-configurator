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
girdle_r_target = max(old_size.x, old_size.z) / 2
height_target = old_size.y

# --- true round-brilliant proportions (unit girdle radius R=1, Y = up) ---
R = 1.0
table_r = 0.53
crown_angle = math.radians(34.5)
pav_angle = math.radians(40.75)
crown_h = (R - table_r) * math.tan(crown_angle)          # table height above girdle
star_r = 0.75                                              # star-point radius (between table and girdle)
star_h = crown_h * 0.42                                    # star points sit partway down the crown
girdle_half = 0.008
lower_girdle_r = 0.60                                       # lower-girdle-facet point radius
lower_girdle_h = -( (R - lower_girdle_r) * math.tan(pav_angle) * 0.5 )
culet_depth = (R) * math.tan(pav_angle)                     # full pavilion depth to culet

bm = bmesh.new()

def vert(r, y, ang_deg):
    a = math.radians(ang_deg)
    return bm.verts.new((r * math.cos(a), y, r * math.sin(a)))

N = 8
T = [vert(table_r, crown_h, i * 45) for i in range(N)]                 # table corners
P = [vert(star_r, star_h, i * 45 + 22.5) for i in range(N)]            # star points
G = [vert(R, girdle_half, i * 45) for i in range(N)]                   # girdle @ bezel angle
H = [vert(R, girdle_half, i * 45 + 22.5) for i in range(N)]            # girdle @ star angle
Gp = [vert(R, -girdle_half, i * 45) for i in range(N)]                 # pavilion-side girdle @ bezel angle
Hp = [vert(R, -girdle_half, i * 45 + 22.5) for i in range(N)]          # pavilion-side girdle @ star angle
L = [vert(lower_girdle_r, lower_girdle_h, i * 45 + 22.5) for i in range(N)]  # lower-girdle facet points
culet = bm.verts.new((0, -culet_depth, 0))

bm.verts.ensure_lookup_table()

# table facet
bm.faces.new(T)

# crown: star facets (triangle: two table corners + one star point)
for i in range(N):
    bm.faces.new((T[i], T[(i + 1) % N], P[i]))

# crown: kite/bezel facets (quad: star point, table corner, star point, girdle point)
for i in range(N):
    p_prev = P[(i - 1) % N]
    bm.faces.new((p_prev, T[i], P[i], G[i]))

# crown: upper girdle facets (16 small triangles either side of each bezel)
for i in range(N):
    bm.faces.new((P[i], G[i], H[i]))
    bm.faces.new((P[i], H[i], G[(i + 1) % N]))

# girdle band (thin rim, 16 quads)
girdle_top = []
girdle_bot = []
for i in range(N):
    girdle_top.append(G[i]); girdle_top.append(H[i])
    girdle_bot.append(Gp[i]); girdle_bot.append(Hp[i])
for i in range(2 * N):
    a0 = girdle_top[i]; a1 = girdle_top[(i + 1) % (2 * N)]
    b0 = girdle_bot[i]; b1 = girdle_bot[(i + 1) % (2 * N)]
    bm.faces.new((a0, a1, b1, b0))

# pavilion: lower girdle facets (16 small triangles)
for i in range(N):
    bm.faces.new((Hp[i], Gp[i], L[i]))
    bm.faces.new((Hp[i], L[i], Gp[(i + 1) % N]))

# pavilion: main pavilion facets (8 large kites down to culet)
for i in range(N):
    l_prev = L[(i - 1) % N]
    bm.faces.new((l_prev, Gp[i], L[i], culet))

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

new_mesh = bpy.data.meshes.new("DiamondGem_RB57")
bm.to_mesh(new_mesh)
bm.free()

raw_height = crown_h + culet_depth
scale_xz = girdle_r_target / R
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

# tighten the gem shader: sharper, more transmissive, precise dispersion-ish IOR
if diamond_mat:
    bsdf = diamond_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Roughness"].default_value = 0.02
        bsdf.inputs["IOR"].default_value = 2.417
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 1.0

diamond_obj.data = new_mesh
new_mesh.materials.append(diamond_mat)
if old_mesh.users == 0:
    bpy.data.meshes.remove(old_mesh)

bpy.context.view_layer.objects.active = diamond_obj
bpy.ops.object.select_all(action='DESELECT')
diamond_obj.select_set(True)
bpy.ops.object.shade_flat()

scene = bpy.context.scene
scene.render.filepath = os.path.join(out_dir, "render_rb57.png")
bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=blend_path)

glb_path = os.path.join(out_dir, "ring.glb")
bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=False, export_apply=True)
print("DONE facets:", len(new_mesh.polygons))
