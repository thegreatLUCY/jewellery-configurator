import bpy, os

out_dir = "/private/tmp/claude-501/-Users-robeirtoma/218035ca-7e83-4096-a998-68e093b899ac/scratchpad/ring_mvp"
blend_path = os.path.join(out_dir, "ring_final.blend")

bpy.ops.wm.open_mainfile(filepath=blend_path)
band = bpy.data.objects["Band"]
gold_mat = bpy.data.materials["Gold"]

# --- UV unwrap the band (it has none) so we can bake a real texture ---
bpy.context.view_layer.objects.active = band
bpy.ops.object.select_all(action='DESELECT')
band.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.0472, island_margin=0.02)
bpy.ops.object.mode_set(mode='OBJECT')

# --- build a procedural micro-roughness node graph feeding a bake target ---
nt = gold_mat.node_tree
nodes = nt.nodes
links = nt.links
bsdf = nodes.get("Principled BSDF")
bsdf.inputs["Roughness"].default_value = 0.14
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Base Color"].default_value = (1.0, 0.766, 0.336, 1.0)

tex_coord = nodes.new("ShaderNodeTexCoord")
noise = nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 60.0
noise.inputs["Detail"].default_value = 4.0
noise.inputs["Roughness"].default_value = 0.6
map_range = nodes.new("ShaderNodeMapRange")
map_range.inputs["To Min"].default_value = 0.08
map_range.inputs["To Max"].default_value = 0.22

links.new(tex_coord.outputs["Generated"], noise.inputs["Vector"])
links.new(noise.outputs["Fac"], map_range.inputs["Value"])
links.new(map_range.outputs["Result"], bsdf.inputs["Roughness"])

# bake target image + node
img = bpy.data.images.new("Gold_Roughness_Bake", width=1024, height=1024, is_data=True)
img_node = nodes.new("ShaderNodeTexImage")
img_node.image = img
img_node.select = True
nodes.active = img_node

# --- bake with Cycles ---
scene = bpy.context.scene
prev_engine = scene.render.engine
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.bake_type = 'ROUGHNESS'
bpy.context.view_layer.objects.active = band
bpy.ops.object.bake(type='ROUGHNESS')

bake_path = os.path.join(out_dir, "gold_roughness_bake.png")
img.filepath_raw = bake_path
img.file_format = 'PNG'
img.save()
print("Baked roughness texture:", bake_path)

# now wire the BAKED image (not the procedural graph) into roughness for export
links.new(img_node.outputs["Color"], bsdf.inputs["Roughness"])
img.colorspace_settings.name = 'Non-Color'

# restore render engine for the preview render
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        continue

scene.render.filepath = os.path.join(out_dir, "render_gold.png")
bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=blend_path)

glb_path = os.path.join(out_dir, "ring.glb")
bpy.ops.export_scene.gltf(filepath=glb_path, export_format='GLB', use_selection=False, export_apply=True)
print("DONE")
