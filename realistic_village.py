import bpy
import random
import math

# -------------------------------------------------
# إعدادات عامة
# -------------------------------------------------
RANDOM_SEED = 1973
random.seed(RANDOM_SEED)



def add_node(nt, node_types, location=(0, 0)):
    if isinstance(node_types, str):
        node_types = [node_types]

    last_error = None
    for node_type in node_types:
        try:
            node = nt.nodes.new(node_type)
            node.location = location
            return node
        except Exception as err:
            last_error = err

    raise RuntimeError(f"Could not create any node type from: {node_types}. Last error: {last_error}")


def set_input_value(node, input_names, value):
    if isinstance(input_names, str):
        input_names = [input_names]

    for input_name in input_names:
        socket = node.inputs.get(input_name)
        if socket is not None:
            socket.default_value = value
            return True
    return False


def get_input_socket(node, preferred_names, fallback_index=None):
    if isinstance(preferred_names, str):
        preferred_names = [preferred_names]

    for input_name in preferred_names:
        socket = node.inputs.get(input_name)
        if socket is not None:
            return socket

    if fallback_index is not None and len(node.inputs) > fallback_index:
        return node.inputs[fallback_index]

    raise RuntimeError(f"Missing input socket {preferred_names} on node {node.bl_idname}")



def configure_mix_node(mix_node, blend_mode='MIX'):
    # MixRGB (قديم) يستخدم blend_type، بينما Mix (حديث) قد يستخدم data_type/factor_mode فقط.
    if hasattr(mix_node, 'blend_type'):
        try:
            mix_node.blend_type = blend_mode
        except Exception:
            pass

    if hasattr(mix_node, 'data_type'):
        try:
            mix_node.data_type = 'RGBA'
        except Exception:
            try:
                mix_node.data_type = 'FLOAT'
            except Exception:
                pass

    if hasattr(mix_node, 'factor_mode'):
        try:
            mix_node.factor_mode = 'UNIFORM'
        except Exception:
            pass

def apply_auto_smooth(obj, angle_degrees=35):
    if obj.type != 'MESH' or obj.data is None:
        return

    try:
        for poly in obj.data.polygons:
            poly.use_smooth = True
    except Exception:
        pass

    # توافق مع API مختلفة
    if hasattr(obj.data, 'use_auto_smooth'):
        obj.data.use_auto_smooth = True
        if hasattr(obj.data, 'auto_smooth_angle'):
            obj.data.auto_smooth_angle = math.radians(angle_degrees)


def move_to_collection(obj, collection_name):
    scene = bpy.context.scene
    target = bpy.data.collections.get(collection_name)
    if target is None:
        target = bpy.data.collections.new(collection_name)
        scene.collection.children.link(target)

    # فك الربط من المجموعات الحالية ثم الربط بالهدف
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    target.objects.link(obj)


def setup_render_and_world(scene):
    # محرك الرندر
    if hasattr(scene, 'render'):
        scene.render.engine = 'CYCLES'
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = 100

    if hasattr(scene, 'cycles'):
        scene.cycles.samples = 192
        if hasattr(scene.cycles, 'use_adaptive_sampling'):
            scene.cycles.use_adaptive_sampling = True
        if hasattr(scene.cycles, 'max_bounces'):
            scene.cycles.max_bounces = 8

    if hasattr(scene, 'view_settings'):
        scene.view_settings.view_transform = 'Filmic'
        scene.view_settings.look = 'Medium High Contrast'
        scene.view_settings.exposure = 0.15

    # الضباب الخفيف للمسافة (Mist)
    if hasattr(scene, 'world') and scene.world is not None:
        world = scene.world
        world.use_nodes = True
        bg = world.node_tree.nodes.get('Background')
        if bg:
            bg.inputs['Color'].default_value = (0.70, 0.83, 1.0, 1)
            bg.inputs['Strength'].default_value = 0.9

        if hasattr(world, 'mist_settings'):
            world.mist_settings.use_mist = True
            world.mist_settings.start = 35
            world.mist_settings.depth = 250
            world.mist_settings.falloff = 'QUADRATIC'

def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.curves:
        if block.users == 0:
            bpy.data.curves.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


# -------------------------------------------------
# خامات واقعية (PBR-like) عبر Nodes
# -------------------------------------------------
def new_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = add_node(nt, 'ShaderNodeOutputMaterial', (500, 0))
    bsdf = add_node(nt, 'ShaderNodeBsdfPrincipled', (250, 0))
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat, nt, bsdf


def create_ground_material():
    mat, nt, bsdf = new_material('GroundSoil')

    noise = add_node(nt, 'ShaderNodeTexNoise', (-650, 120))
    noise.inputs['Scale'].default_value = 18
    noise.inputs['Detail'].default_value = 12
    noise.inputs['Roughness'].default_value = 0.6

    wave = add_node(nt, 'ShaderNodeTexWave', (-650, -90))
    wave.inputs['Scale'].default_value = 5
    wave.inputs['Distortion'].default_value = 9

    mix = add_node(nt, ['ShaderNodeMixRGB', 'ShaderNodeMix'], (-430, 20))
    configure_mix_node(mix, 'MULTIPLY')
    set_input_value(mix, ['Fac', 'Factor'], 0.5)

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-250, 30))
    ramp.color_ramp.elements[0].color = (0.18, 0.12, 0.08, 1)
    ramp.color_ramp.elements[1].color = (0.42, 0.33, 0.22, 1)

    bump = add_node(nt, 'ShaderNodeBump', (20, -130))
    bump.inputs['Strength'].default_value = 0.25

    nt.links.new(noise.outputs['Fac'], get_input_socket(mix, ['Color1', 'A'], 6))
    nt.links.new(wave.outputs['Color'], get_input_socket(mix, ['Color2', 'B'], 7))
    nt.links.new(mix.outputs['Color'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.95

    return mat


def create_mud_wall_material():
    mat, nt, bsdf = new_material('MudWall')

    noise = add_node(nt, 'ShaderNodeTexNoise', (-530, 100))
    noise.inputs['Scale'].default_value = 9
    noise.inputs['Detail'].default_value = 5

    musgrave = add_node(nt, ['ShaderNodeTexMusgrave', 'ShaderNodeTexNoise'], (-530, -90))
    musgrave.inputs['Scale'].default_value = 21
    musgrave.inputs['Detail'].default_value = 8

    mix = add_node(nt, ['ShaderNodeMixRGB', 'ShaderNodeMix'], (-330, 0))
    configure_mix_node(mix, 'OVERLAY')
    set_input_value(mix, ['Fac', 'Factor'], 0.55)

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-140, 0))
    ramp.color_ramp.elements[0].color = (0.32, 0.22, 0.14, 1)
    ramp.color_ramp.elements[1].color = (0.66, 0.49, 0.31, 1)

    bump = add_node(nt, 'ShaderNodeBump', (40, -120))
    bump.inputs['Strength'].default_value = 0.45

    nt.links.new(noise.outputs['Fac'], get_input_socket(mix, ['Color1', 'A'], 6))
    nt.links.new(musgrave.outputs['Fac'], get_input_socket(mix, ['Color2', 'B'], 7))
    nt.links.new(mix.outputs['Color'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(musgrave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    bsdf.inputs['Roughness'].default_value = 0.88
    set_input_value(bsdf, ['Specular IOR Level', 'Specular'], 0.15)
    return mat


def create_stone_material():
    mat, nt, bsdf = new_material('StoneRock')

    noise = add_node(nt, 'ShaderNodeTexNoise', (-510, 120))
    noise.inputs['Scale'].default_value = 12
    noise.inputs['Detail'].default_value = 14

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-280, 100))
    ramp.color_ramp.elements[0].color = (0.18, 0.18, 0.17, 1)
    ramp.color_ramp.elements[1].color = (0.45, 0.43, 0.41, 1)

    bump = add_node(nt, 'ShaderNodeBump', (-80, -80))
    bump.inputs['Strength'].default_value = 0.6

    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    bsdf.inputs['Roughness'].default_value = 0.78
    return mat


def create_leaf_material():
    mat, nt, bsdf = new_material('PalmLeaf')
    noise = add_node(nt, 'ShaderNodeTexNoise', (-350, 100))
    noise.inputs['Scale'].default_value = 6

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-150, 100))
    ramp.color_ramp.elements[0].color = (0.05, 0.15, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.28, 0.45, 0.12, 1)

    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.84
    return mat


def create_water_material():
    mat, nt, bsdf = new_material('FalajWater')
    bsdf.inputs['Base Color'].default_value = (0.04, 0.16, 0.18, 1)
    if not set_input_value(bsdf, ['Transmission Weight', 'Transmission'], 0.85):
        set_input_value(bsdf, ['Alpha'], 0.95)
    bsdf.inputs['Roughness'].default_value = 0.1
    bsdf.inputs['IOR'].default_value = 1.333

    wave = add_node(nt, 'ShaderNodeTexWave', (-450, -90))
    wave.inputs['Scale'].default_value = 22
    wave.inputs['Distortion'].default_value = 7

    noise = add_node(nt, 'ShaderNodeTexNoise', (-450, 80))
    noise.inputs['Scale'].default_value = 10
    noise.inputs['Detail'].default_value = 8

    mix = add_node(nt, ['ShaderNodeMixRGB', 'ShaderNodeMix'], (-240, -10))
    configure_mix_node(mix, 'ADD')
    set_input_value(mix, ['Fac', 'Factor'], 0.35)

    bump = add_node(nt, 'ShaderNodeBump', (-20, -110))
    bump.inputs['Strength'].default_value = 0.08

    nt.links.new(wave.outputs['Color'], get_input_socket(mix, ['Color1', 'A'], 6))
    nt.links.new(noise.outputs['Color'], get_input_socket(mix, ['Color2', 'B'], 7))
    nt.links.new(mix.outputs['Color'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


# -------------------------------------------------
# أدوات تعديل المجسمات (نحت/خشونة)
# -------------------------------------------------
def add_displace(obj, strength=1.0, scale=3.0):
    tex = bpy.data.textures.new(f"{obj.name}_disp", type='CLOUDS')
    tex.noise_scale = scale
    mod = obj.modifiers.new('Displace', type='DISPLACE')
    mod.texture = tex
    mod.strength = strength


def add_subsurf(obj, level=2):
    mod = obj.modifiers.new('Subsurf', type='SUBSURF')
    mod.levels = level
    mod.render_levels = level


def add_bevel(obj, width=0.15):
    mod = obj.modifiers.new('Bevel', type='BEVEL')
    mod.width = width
    mod.segments = 2


# -------------------------------------------------
# تفاصيل إضافية للمشهد
# -------------------------------------------------
def create_wood_material():
    mat, nt, bsdf = new_material('Wood')
    wave = add_node(nt, 'ShaderNodeTexWave', (-420, 80))
    wave.inputs['Scale'].default_value = 14
    wave.inputs['Distortion'].default_value = 2.2

    noise = add_node(nt, 'ShaderNodeTexNoise', (-420, -90))
    noise.inputs['Scale'].default_value = 5

    mix = add_node(nt, ['ShaderNodeMixRGB', 'ShaderNodeMix'], (-220, 0))
    configure_mix_node(mix, 'MULTIPLY')
    set_input_value(mix, ['Fac', 'Factor'], 0.45)

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-40, 0))
    ramp.color_ramp.elements[0].color = (0.18, 0.10, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.40, 0.24, 0.09, 1)

    nt.links.new(wave.outputs['Color'], get_input_socket(mix, ['Color1', 'A'], 6))
    nt.links.new(noise.outputs['Color'], get_input_socket(mix, ['Color2', 'B'], 7))
    nt.links.new(mix.outputs['Color'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.75
    return mat


def create_plaster_material():
    mat, nt, bsdf = new_material('Plaster')
    noise = add_node(nt, 'ShaderNodeTexNoise', (-300, 80))
    noise.inputs['Scale'].default_value = 22
    noise.inputs['Detail'].default_value = 10

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-80, 80))
    ramp.color_ramp.elements[0].color = (0.70, 0.64, 0.54, 1)
    ramp.color_ramp.elements[1].color = (0.90, 0.84, 0.72, 1)

    bump = add_node(nt, 'ShaderNodeBump', (80, -40))
    bump.inputs['Strength'].default_value = 0.18

    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.86
    return mat


def add_house_details(base_x, base_y, body_h, wood_mat, plaster_mat):
    door_h = max(1.0, body_h * 0.35)
    window_h = max(1.8, body_h * 0.75)

    # باب
    bpy.ops.mesh.primitive_cube_add(location=(base_x, base_y + 5.05, door_h))
    door = bpy.context.object
    door.scale = (0.9, 0.08, door_h)
    door.data.materials.append(wood_mat)
    move_to_collection(door, 'Architecture')
    apply_auto_smooth(door, 30)

    # نافذتان
    for offset in (-1.7, 1.7):
        bpy.ops.mesh.primitive_cube_add(location=(base_x + offset, base_y + 5.07, window_h))
        window = bpy.context.object
        window.scale = (0.6, 0.05, 0.5)
        window.data.materials.append(plaster_mat)
        move_to_collection(window, 'Architecture')


def create_perimeter_wall(stone_mat):
    segments = [
        ((0, 36, 1.3), (42, 1.0, 1.3)),
        ((0, -36, 1.3), (42, 1.0, 1.3)),
        ((36, 0, 1.3), (1.0, 36, 1.3)),
        ((-36, 0, 1.3), (1.0, 36, 1.3)),
    ]
    for loc, scl in segments:
        bpy.ops.mesh.primitive_cube_add(location=loc)
        wall = bpy.context.object
        wall.scale = scl
        wall.data.materials.append(stone_mat)
        move_to_collection(wall, 'Architecture')
        add_bevel(wall, 0.12)
        add_displace(wall, strength=0.25, scale=1.7)


def add_path_lamps(wood_mat):
    for i in range(8):
        x = -28 + i * 8
        y = -12 + math.sin(i * 0.7) * 2.5
        bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=3.2, location=(x, y, 1.6))
        pole = bpy.context.object
        pole.data.materials.append(wood_mat)
        move_to_collection(pole, 'Props')

        bpy.ops.object.light_add(type='POINT', location=(x, y, 3.3))
        lamp = bpy.context.object
        lamp.data.energy = 45
        lamp.data.color = (1.0, 0.87, 0.72)
        move_to_collection(lamp, 'Lights')

# -------------------------------------------------
# توسعات معمارية وحياة يومية
# -------------------------------------------------
def create_fabric_material():
    mat, nt, bsdf = new_material('Fabric')
    noise = add_node(nt, 'ShaderNodeTexNoise', (-280, 80))
    noise.inputs['Scale'].default_value = 26
    noise.inputs['Detail'].default_value = 6

    ramp = add_node(nt, 'ShaderNodeValToRGB', (-80, 80))
    ramp.color_ramp.elements[0].color = (0.45, 0.18, 0.08, 1)
    ramp.color_ramp.elements[1].color = (0.86, 0.62, 0.26, 1)

    bump = add_node(nt, 'ShaderNodeBump', (100, -40))
    bump.inputs['Strength'].default_value = 0.08

    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.92
    return mat


def create_market_zone(wood_mat, fabric_mat, ground_mat):
    stall_positions = [(-14, -6), (-6, -8), (3, -7), (11, -6)]
    for sx, sy in stall_positions:
        bpy.ops.mesh.primitive_cube_add(location=(sx, sy, 0.9))
        base = bpy.context.object
        base.scale = (2.1, 1.3, 0.9)
        base.data.materials.append(wood_mat)
        move_to_collection(base, 'Props')
        apply_auto_smooth(base, 30)

        bpy.ops.mesh.primitive_plane_add(size=3.8, location=(sx, sy, 2.2))
        canopy = bpy.context.object
        canopy.rotation_euler[0] = math.radians(4)
        canopy.data.materials.append(fabric_mat)
        move_to_collection(canopy, 'Props')

        # صناديق بسيطة حول السوق
        for _ in range(3):
            ox = sx + random.uniform(-1.6, 1.6)
            oy = sy + random.uniform(-1.1, 1.1)
            bpy.ops.mesh.primitive_cube_add(location=(ox, oy, 0.35))
            crate = bpy.context.object
            crate.scale = (0.35, 0.35, 0.35)
            crate.data.materials.append(wood_mat)
            move_to_collection(crate, 'Props')

    # أرضية السوق
    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, -8, 0.025))
    market_ground = bpy.context.object
    market_ground.data.materials.append(ground_mat)
    move_to_collection(market_ground, 'Props')


def create_watch_tower(stone_mat, wood_mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=3.2, depth=13, location=(-32, 30, 6.5))
    tower = bpy.context.object
    tower.data.materials.append(stone_mat)
    move_to_collection(tower, 'Architecture')
    add_bevel(tower, 0.18)
    add_displace(tower, strength=0.35, scale=1.4)
    apply_auto_smooth(tower, 40)

    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=4.2, depth=3.1, location=(-32, 30, 14.6))
    roof = bpy.context.object
    roof.rotation_euler[2] = math.radians(45)
    roof.data.materials.append(wood_mat)
    move_to_collection(roof, 'Architecture')


def add_footpath_stones(stone_mat):
    for i in range(55):
        x = -26 + i * 0.9
        y = 8 + math.sin(i * 0.35) * 2.0
        bpy.ops.mesh.primitive_cube_add(location=(x, y, 0.12))
        stone = bpy.context.object
        stone.scale = (0.22 + random.uniform(-0.08, 0.1), 0.22 + random.uniform(-0.08, 0.1), 0.08)
        stone.rotation_euler[2] = random.uniform(-0.5, 0.5)
        stone.data.materials.append(stone_mat)
        move_to_collection(stone, 'Props')

# -------------------------------------------------
# تحسينات سينمائية وتفاصيل بيئية أخيرة
# -------------------------------------------------
def setup_compositor(scene):
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()

    rl = nt.nodes.new('CompositorNodeRLayers')
    rl.location = (-280, 0)

    glare = nt.nodes.new('CompositorNodeGlare')
    glare.location = (-20, 0)
    glare.glare_type = 'FOG_GLOW'
    glare.quality = 'HIGH'
    glare.threshold = 0.85
    glare.size = 6

    color_balance = nt.nodes.new('CompositorNodeColorBalance')
    color_balance.location = (220, 0)
    color_balance.lift = (0.99, 1.0, 1.02)
    color_balance.gamma = (1.01, 1.0, 0.98)
    color_balance.gain = (1.03, 1.01, 0.97)

    vignette = nt.nodes.new('CompositorNodeEllipseMask')
    vignette.location = (-20, -220)
    vignette.width = 0.88
    vignette.height = 0.78

    blur = nt.nodes.new('CompositorNodeBlur')
    blur.location = (220, -220)
    blur.filter_type = 'GAUSS'
    blur.size_x = 240
    blur.size_y = 240

    mix = nt.nodes.new('CompositorNodeMixRGB')
    mix.location = (440, -20)
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Fac'].default_value = 0.25

    comp = nt.nodes.new('CompositorNodeComposite')
    comp.location = (670, 10)

    nt.links.new(rl.outputs['Image'], glare.inputs['Image'])
    nt.links.new(glare.outputs['Image'], color_balance.inputs['Image'])
    nt.links.new(vignette.outputs['Mask'], blur.inputs['Image'])
    nt.links.new(color_balance.outputs['Image'], mix.inputs['Color1'])
    nt.links.new(blur.outputs['Image'], mix.inputs['Color2'])
    nt.links.new(mix.outputs['Image'], comp.inputs['Image'])


def add_well_feature(stone_mat, wood_mat, water_mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=2.1, depth=1.6, location=(9, 10, 0.8))
    well = bpy.context.object
    well.data.materials.append(stone_mat)
    move_to_collection(well, 'Props')
    add_bevel(well, 0.08)
    add_displace(well, strength=0.1, scale=1.1)

    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1.4, depth=0.24, location=(9, 10, 0.55))
    water = bpy.context.object
    water.data.materials.append(water_mat)
    move_to_collection(water, 'Props')

    for x_sign in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=2.4, location=(9 + x_sign*1.45, 10, 2.15))
        post = bpy.context.object
        post.data.materials.append(wood_mat)
        move_to_collection(post, 'Props')

    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=3.0, location=(9, 10, 3.15))
    beam = bpy.context.object
    beam.rotation_euler[1] = math.radians(90)
    beam.data.materials.append(wood_mat)
    move_to_collection(beam, 'Props')


def setup_camera_dof(cam, focus_distance=46.0):
    if cam and cam.data and hasattr(cam.data, 'dof'):
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = focus_distance
        if hasattr(cam.data.dof, 'aperture_fstop'):
            cam.data.dof.aperture_fstop = 4.0

# -------------------------------------------------
# لمسات حياة إضافية (نار/دخان/طيور)
# -------------------------------------------------
def create_smoke_material():
    mat, nt, bsdf = new_material('SmokeTint')
    bsdf.inputs['Base Color'].default_value = (0.24, 0.24, 0.24, 1)
    bsdf.inputs['Roughness'].default_value = 1.0
    set_input_value(bsdf, ['Alpha'], 0.15)
    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else 'OPAQUE'
    return mat


def add_campfire_area(wood_mat, stone_mat):
    cx, cy = -4, 6

    # حلقة حجارة
    for i in range(12):
        ang = i * (math.tau / 12)
        x = cx + math.cos(ang) * 1.2
        y = cy + math.sin(ang) * 1.2
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.22, location=(x, y, 0.2))
        rock = bpy.context.object
        rock.scale = (1.0, 0.8, 0.6)
        rock.data.materials.append(stone_mat)
        move_to_collection(rock, 'Props')

    # حطب
    for tilt in (-0.55, -0.2, 0.2, 0.55):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=1.8, location=(cx, cy, 0.32))
        log = bpy.context.object
        log.rotation_euler[2] = tilt
        log.rotation_euler[0] = math.radians(82)
        log.data.materials.append(wood_mat)
        move_to_collection(log, 'Props')

    # ضوء النار
    bpy.ops.object.light_add(type='POINT', location=(cx, cy, 0.75))
    fire = bpy.context.object
    fire.data.energy = 130
    fire.data.color = (1.0, 0.48, 0.15)
    move_to_collection(fire, 'Lights')


def add_smoke_column(smoke_mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(-4, 6, 1.2))
    puff1 = bpy.context.object
    puff1.scale = (1.1, 1.1, 0.7)
    puff1.data.materials.append(smoke_mat)
    move_to_collection(puff1, 'FX')

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, location=(-3.8, 6.1, 2.0))
    puff2 = bpy.context.object
    puff2.scale = (1.3, 1.2, 0.8)
    puff2.data.materials.append(smoke_mat)
    move_to_collection(puff2, 'FX')


def add_bird_flock(stone_mat):
    for i in range(18):
        x = -70 + i * 8 + random.uniform(-1.5, 1.5)
        y = 20 + math.sin(i * 0.6) * 9
        z = 38 + random.uniform(-2.0, 3.5)
        bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.45, depth=0.18, location=(x, y, z))
        bird = bpy.context.object
        bird.rotation_euler[0] = math.radians(90)
        bird.rotation_euler[2] = random.uniform(-0.3, 0.3)
        bird.data.materials.append(stone_mat)
        move_to_collection(bird, 'FX')

# -------------------------------------------------
# إنشاء البيئة
# -------------------------------------------------
def build_scene():
    clean_scene()

    mud_mat = create_mud_wall_material()
    ground_mat = create_ground_material()
    stone_mat = create_stone_material()
    leaf_mat = create_leaf_material()
    water_mat = create_water_material()
    wood_mat = create_wood_material()
    plaster_mat = create_plaster_material()
    fabric_mat = create_fabric_material()
    smoke_mat = create_smoke_material()

    # أرض كبيرة مع تفاصيل نحت بسيطة
    bpy.ops.mesh.primitive_plane_add(size=240, location=(0, 0, 0))
    ground = bpy.context.object
    ground.data.materials.append(ground_mat)
    move_to_collection(ground, 'Terrain')
    apply_auto_smooth(ground, 40)
    add_subsurf(ground, 3)
    add_displace(ground, strength=2.2, scale=9.0)

    # جبال خلفية مع شكل غير منتظم
    for i in range(8):
        bpy.ops.mesh.primitive_cube_add(location=(-90 + i * 25, 95, 16))
        m = bpy.context.object
        m.scale = (13 + random.uniform(-2, 3), 13 + random.uniform(-2, 3), random.uniform(17, 38))
        m.data.materials.append(stone_mat)
        move_to_collection(m, 'Mountains')
        apply_auto_smooth(m, 45)
        add_bevel(m, 0.35)
        add_displace(m, strength=3.4, scale=4.8)

    # تل + حصن
    bpy.ops.mesh.primitive_cone_add(radius1=20, depth=13, location=(62, 58, 6.5), vertices=48)
    hill = bpy.context.object
    hill.data.materials.append(stone_mat)
    move_to_collection(hill, 'Terrain')
    apply_auto_smooth(hill, 45)
    add_displace(hill, strength=1.5, scale=2.2)

    bpy.ops.mesh.primitive_cube_add(location=(62, 58, 17))
    fort = bpy.context.object
    fort.scale = (11, 11, 8.5)
    fort.data.materials.append(mud_mat)
    move_to_collection(fort, 'Architecture')
    apply_auto_smooth(fort, 30)
    add_bevel(fort, 0.4)

    # ساحة القرية
    bpy.ops.mesh.primitive_plane_add(size=28, location=(0, 0, 0.03))
    square = bpy.context.object
    square.data.materials.append(ground_mat)
    move_to_collection(square, 'Terrain')

    create_perimeter_wall(stone_mat)
    create_watch_tower(stone_mat, wood_mat)

    # بيوت متنوعة مع أسقف
    house_positions = [
        (-20, 15), (-10, 20), (0, 18),
        (20, 15), (10, 20), (0, -20),
        (-15, -15), (15, -15), (-25, 0), (25, 0)
    ]

    for pos in house_positions:
        h_height = random.uniform(2.8, 5.5)
        bpy.ops.mesh.primitive_cube_add(location=(pos[0], pos[1], h_height / 2))
        house = bpy.context.object
        house.scale = (4 + random.uniform(-0.8, 1.1), 5 + random.uniform(-0.9, 0.8), h_height)
        house.rotation_euler[2] = random.uniform(-0.15, 0.15)
        house.data.materials.append(mud_mat)
        move_to_collection(house, 'Architecture')
        apply_auto_smooth(house, 30)
        add_bevel(house, 0.2)

        # سقف بسيط
        bpy.ops.mesh.primitive_cone_add(radius1=house.scale.x * 1.1, depth=2.2,
                                        location=(pos[0], pos[1], h_height * 2 + 0.8), vertices=4)
        roof = bpy.context.object
        roof.rotation_euler[2] = math.radians(45) + house.rotation_euler[2]
        roof.data.materials.append(stone_mat)
        move_to_collection(roof, 'Architecture')
        apply_auto_smooth(roof, 35)

        add_house_details(pos[0], pos[1], h_height, wood_mat, plaster_mat)

    # فلج مع مجرى ماء
    mesh = bpy.data.meshes.new('FalajChannel')
    falaj = bpy.data.objects.new('FalajChannel', mesh)
    bpy.context.collection.objects.link(falaj)
    move_to_collection(falaj, 'WaterSystem')

    verts = []
    faces = []
    width = 1.8
    depth = -0.4
    length = 82
    segments = 36

    for i in range(segments + 1):
        x = -40 + i * (length / segments)
        y = math.sin(i * 0.4) * 4.8
        verts.extend([
            (x, y - width, 0.08),
            (x, y + width, 0.08),
            (x, y - width * 0.55, depth),
            (x, y + width * 0.55, depth),
        ])

    for i in range(0, len(verts) - 4, 4):
        faces.extend([
            (i, i + 1, i + 5, i + 4),
            (i + 2, i + 3, i + 7, i + 6),
            (i, i + 2, i + 6, i + 4),
            (i + 1, i + 3, i + 7, i + 5),
        ])

    mesh.from_pydata(verts, [], faces)
    mesh.update()
    falaj.data.materials.append(stone_mat)
    apply_auto_smooth(falaj, 40)

    # طبقة الماء فوق المجرى
    water_mesh = bpy.data.meshes.new('FalajWaterMesh')
    water_obj = bpy.data.objects.new('FalajWater', water_mesh)
    bpy.context.collection.objects.link(water_obj)
    move_to_collection(water_obj, 'WaterSystem')

    w_verts = []
    w_faces = []
    for i in range(segments + 1):
        x = -40 + i * (length / segments)
        y = math.sin(i * 0.4) * 4.8
        w_verts.append((x, y - width * 0.5, -0.08))
        w_verts.append((x, y + width * 0.5, -0.08))
    for i in range(0, len(w_verts) - 2, 2):
        w_faces.append((i, i + 1, i + 3, i + 2))

    water_mesh.from_pydata(w_verts, [], w_faces)
    water_mesh.update()
    water_obj.data.materials.append(water_mat)
    apply_auto_smooth(water_obj, 50)

    # شارع ترابي متعرج
    bpy.ops.curve.primitive_bezier_curve_add(location=(0, -60, 0.02))
    road = bpy.context.object
    road.scale = (1.4, 84, 1)
    road.data.bevel_depth = 0.4
    bpy.ops.object.convert(target='MESH')
    road = bpy.context.object
    road.data.materials.append(ground_mat)
    move_to_collection(road, 'Roads')
    apply_auto_smooth(road, 35)

    create_market_zone(wood_mat, fabric_mat, ground_mat)
    add_footpath_stones(stone_mat)
    add_well_feature(stone_mat, wood_mat, water_mat)
    add_campfire_area(wood_mat, stone_mat)
    add_smoke_column(smoke_mat)
    add_bird_flock(stone_mat)

    # مزارع
    for x in [-60, 60]:
        bpy.ops.mesh.primitive_plane_add(size=44, location=(x, -40, 0.07))
        farm = bpy.context.object
        farm.data.materials.append(leaf_mat)
        move_to_collection(farm, 'Farms')
        add_displace(farm, strength=0.35, scale=1.8)

    # نخيل أكثر طبيعية
    for _ in range(28):
        x = random.uniform(-72, 72)
        y = random.uniform(-62, -15)
        trunk_h = random.uniform(6.5, 10)

        bpy.ops.mesh.primitive_cylinder_add(radius=random.uniform(0.32, 0.6), depth=trunk_h,
                                            location=(x, y, trunk_h / 2), vertices=12)
        trunk = bpy.context.object
        trunk.data.materials.append(mud_mat)
        move_to_collection(trunk, 'Vegetation')
        apply_auto_smooth(trunk, 25)
        trunk.rotation_euler[0] = random.uniform(-0.1, 0.1)
        trunk.rotation_euler[1] = random.uniform(-0.1, 0.1)
        add_displace(trunk, strength=0.16, scale=0.8)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(2.4, 3.6), location=(x, y, trunk_h + 1.8))
        leaves = bpy.context.object
        leaves.scale = (1.1, 0.9, 0.65)
        leaves.data.materials.append(leaf_mat)
        move_to_collection(leaves, 'Vegetation')
        apply_auto_smooth(leaves, 40)

    # كاميرا وإضاءة مناسبة
    bpy.ops.object.light_add(type='SUN', location=(80, -40, 120))
    sun = bpy.context.object
    sun.data.energy = 5.8
    sun.rotation_euler = (math.radians(45), math.radians(5), math.radians(28))
    sun.data.angle = math.radians(1.0)

    bpy.ops.object.camera_add(location=(0, -150, 70), rotation=(math.radians(67), 0, 0))
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    move_to_collection(cam, 'Cameras')
    if hasattr(cam.data, 'lens'):
        cam.data.lens = 40
    setup_camera_dof(cam, 58.0)

    bpy.ops.object.light_add(type='AREA', location=(-50, -120, 40))
    fill = bpy.context.object
    fill.data.energy = 340
    fill.data.size = 25
    move_to_collection(fill, 'Lights')

    bpy.ops.object.light_add(type='AREA', location=(95, 35, 35))
    rim = bpy.context.object
    rim.data.energy = 180
    rim.data.size = 18
    rim.rotation_euler = (math.radians(62), math.radians(0), math.radians(118))
    move_to_collection(rim, 'Lights')

    move_to_collection(sun, 'Lights')

    add_path_lamps(wood_mat)

    # إعدادات أفضل للمشهد
    scene = bpy.context.scene
    setup_render_and_world(scene)
    setup_compositor(scene)

    print('✅ تم تحويل المخطط إلى قرية أكثر واقعية بخامات وتفاصيل نحت طبيعية.')


if __name__ == '__main__':
    build_scene()
