"""
Generates the project's material system and an empty street level.

Run from inside the editor:  Window > Developer Tools > Output Log,
switch the console dropdown to "Python", then:

    exec(open(r"<project>/Tools/build_content.py").read())

What it makes
-------------
  /Game/Materials/M_HopeSurface     one master material, triplanar
  /Game/Materials/MI_Hope_<Key>     an instance per surface
  /Game/Maps/Street                 an empty level

Why a master plus instances rather than a material each: it is the shape the
Megascans path needs. import_megascans.py does nothing but set texture
parameters on these same instances, so plugging real scanned surfaces in is a
parameter assignment, not a rebuild.

Why triplanar: the street is assembled from engine cubes, whose UVs run 0-1 per
face. A brick texture mapped through those UVs would stretch a single tile
across a fifteen-metre facade. WorldAlignedTexture projects from world space
instead, so tiling is in centimetres and identical on every surface regardless
of the box it lands on.

This step is OPTIONAL. Without it HopeBlocks::MaterialFor falls back to a
tinted instance of the engine's basic shape material and the game still runs,
just flat.
"""

import unreal

MATERIAL_DIR = "/Game/Materials"
MAP_DIR = "/Game/Maps"
MASTER_PATH = "{0}/M_HopeSurface".format(MATERIAL_DIR)

# Engine defaults that make an unassigned texture parameter a no-op:
# white multiplies to nothing, and the flat normal leaves the surface alone.
WHITE = "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"
FLAT_NORMAL = "/Engine/EngineMaterials/DefaultNormal.DefaultNormal"

WORLD_ALIGNED_TEXTURE = (
    "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
    "WorldAlignedTexture.WorldAlignedTexture")
WORLD_ALIGNED_NORMAL = (
    "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
    "WorldAlignedNormal.WorldAlignedNormal")

# key -> (tint, roughness, metallic, triplanar tile size in cm)
#
# Tile sizes are the real-world size of one texture repeat, so they read as
# physical: brick courses tile every 1.2 m, road aggregate every 2.5 m.
SURFACES = {
    "Asphalt":  ((0.055, 0.053, 0.050), 0.72, 0.0, 250.0),
    "Sidewalk": ((0.150, 0.142, 0.128), 0.88, 0.0, 180.0),
    "Kerb":     ((0.180, 0.172, 0.158), 0.85, 0.0, 160.0),
    "Dirt":     ((0.110, 0.095, 0.072), 0.95, 0.0, 320.0),
    "Stucco":   ((0.230, 0.212, 0.185), 0.90, 0.0, 220.0),
    "Brick":    ((0.140, 0.088, 0.070), 0.92, 0.0, 120.0),
    "Shutter":  ((0.085, 0.090, 0.092), 0.55, 0.85, 90.0),
    "Sign":     ((0.320, 0.140, 0.095), 0.65, 0.0, 150.0),
    "Awning":   ((0.190, 0.145, 0.110), 0.88, 0.0, 110.0),
    "Glass":    ((0.020, 0.024, 0.028), 0.12, 0.0, 200.0),
    "Metal":    ((0.095, 0.100, 0.105), 0.45, 0.90, 80.0),
    "Leather":  ((0.045, 0.038, 0.034), 0.42, 0.0, 22.0),
    "Fabric":   ((0.055, 0.058, 0.062), 0.88, 0.0, 18.0),
    "Skin":     ((0.420, 0.300, 0.240), 0.62, 0.0, 14.0),
    "Patch":    ((0.180, 0.220, 0.420), 0.70, 0.0, 12.0),
    "Shadow":   ((0.006, 0.005, 0.010), 0.98, 0.0, 60.0),
}

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def expr(material, cls, x, y, **props):
    node = mel.create_material_expression(material, cls, x, y)
    for key, value in props.items():
        node.set_editor_property(key, value)
    return node


def texture_param(material, name, default_path, x, y):
    node = expr(material, unreal.MaterialExpressionTextureObjectParameter, x, y,
                parameter_name=name)
    texture = unreal.load_asset(default_path)
    if texture:
        node.set_editor_property("texture", texture)
    return node


def build_master():
    """
    One material for every surface in the game.

    Every texture parameter defaults to something neutral, so the same graph
    covers both states: with no textures assigned it resolves to a flat tinted
    surface, and with Megascans maps assigned it resolves to the scan. There is
    no switch and no second code path.
    """
    if eal.does_asset_exist(MASTER_PATH):
        eal.delete_asset(MASTER_PATH)

    material = tools.create_asset("M_HopeSurface", MATERIAL_DIR, unreal.Material,
                                  unreal.MaterialFactoryNew())

    wat = unreal.load_asset(WORLD_ALIGNED_TEXTURE)
    wan = unreal.load_asset(WORLD_ALIGNED_NORMAL)
    if not wat or not wan:
        raise RuntimeError("engine triplanar material functions not found")

    tile = expr(material, unreal.MaterialExpressionScalarParameter, -1500, 400,
                parameter_name="TileSize", default_value=200.0)

    # --- base colour -------------------------------------------------------
    base_tex = texture_param(material, "BaseColorMap", WHITE, -1500, -400)
    base_proj = expr(material, unreal.MaterialExpressionMaterialFunctionCall, -1100, -400)
    base_proj.set_editor_property("material_function", wat)
    mel.connect_material_expressions(base_tex, "", base_proj, "TextureObject (T2d)")
    mel.connect_material_expressions(tile, "", base_proj, "TextureSize (S)")

    tint = expr(material, unreal.MaterialExpressionVectorParameter, -1100, -180,
                parameter_name="BaseColorTint",
                default_value=unreal.LinearColor(0.5, 0.5, 0.5, 1.0))

    base = expr(material, unreal.MaterialExpressionMultiply, -700, -320)
    mel.connect_material_expressions(base_proj, "XYZ Texture", base, "A")
    mel.connect_material_expressions(tint, "", base, "B")
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # --- normal ------------------------------------------------------------
    normal_tex = texture_param(material, "NormalMap", FLAT_NORMAL, -1500, 0)
    normal_proj = expr(material, unreal.MaterialExpressionMaterialFunctionCall, -1100, 40)
    normal_proj.set_editor_property("material_function", wan)
    mel.connect_material_expressions(normal_tex, "", normal_proj, "TextureObject (T2d)")
    mel.connect_material_expressions(tile, "", normal_proj, "TextureSize (S)")
    mel.connect_material_property(normal_proj, "", unreal.MaterialProperty.MP_NORMAL)

    # --- roughness ---------------------------------------------------------
    # Megascans packs occlusion/roughness/displacement into one RGB map, which
    # is why roughness is read from green rather than from a dedicated texture.
    ord_tex = texture_param(material, "ORDMap", WHITE, -1500, 700)
    ord_proj = expr(material, unreal.MaterialExpressionMaterialFunctionCall, -1100, 700)
    ord_proj.set_editor_property("material_function", wat)
    mel.connect_material_expressions(ord_tex, "", ord_proj, "TextureObject (T2d)")
    mel.connect_material_expressions(tile, "", ord_proj, "TextureSize (S)")

    rough_param = expr(material, unreal.MaterialExpressionScalarParameter, -1100, 900,
                       parameter_name="Roughness", default_value=0.8)
    rough = expr(material, unreal.MaterialExpressionMultiply, -700, 780)
    mel.connect_material_expressions(ord_proj, "G", rough, "A")
    mel.connect_material_expressions(rough_param, "", rough, "B")
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    # --- metallic ----------------------------------------------------------
    metal = expr(material, unreal.MaterialExpressionScalarParameter, -700, 1020,
                 parameter_name="Metallic", default_value=0.0)
    mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)

    # --- emissive ----------------------------------------------------------
    # Driven at runtime: the shadows glow from inside when hit.
    emissive_tint = expr(material, unreal.MaterialExpressionVectorParameter, -1100, 1200,
                         parameter_name="EmissiveTint",
                         default_value=unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    emissive_str = expr(material, unreal.MaterialExpressionScalarParameter, -1100, 1360,
                        parameter_name="EmissiveStrength", default_value=0.0)
    emissive = expr(material, unreal.MaterialExpressionMultiply, -700, 1260)
    mel.connect_material_expressions(emissive_tint, "", emissive, "A")
    mel.connect_material_expressions(emissive_str, "", emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.recompile_material(material)
    eal.save_asset(MASTER_PATH)
    return material


def build_instance(master, key, tint, roughness, metallic, tile):
    name = "MI_Hope_{0}".format(key)
    path = "{0}/{1}".format(MATERIAL_DIR, name)

    if eal.does_asset_exist(path):
        eal.delete_asset(path)

    instance = tools.create_asset(name, MATERIAL_DIR, unreal.MaterialInstanceConstant,
                                  unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(instance, master)
    mel.set_material_instance_vector_parameter_value(
        instance, "BaseColorTint", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
    mel.set_material_instance_scalar_parameter_value(instance, "Roughness", roughness)
    mel.set_material_instance_scalar_parameter_value(instance, "Metallic", metallic)
    mel.set_material_instance_scalar_parameter_value(instance, "TileSize", tile)

    eal.save_asset(path)
    return path


def build_level():
    """An empty level. AHopeStreet builds itself into it at BeginPlay."""
    path = "{0}/Street".format(MAP_DIR)
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    subsystem.new_level(path)
    subsystem.save_current_level()
    return path


def run():
    try:
        master = build_master()
    except Exception as error:                          # noqa: BLE001
        unreal.log_error("master material failed, nothing else can proceed: {0}".format(error))
        return

    made = 0
    for key, (tint, roughness, metallic, tile) in SURFACES.items():
        try:
            build_instance(master, key, tint, roughness, metallic, tile)
            made += 1
        except Exception as error:                      # noqa: BLE001
            unreal.log_error("MI_Hope_{0} failed: {1}".format(key, error))

    unreal.log("built {0}/{1} material instances".format(made, len(SURFACES)))

    try:
        unreal.log("level: {0}".format(build_level()))
    except Exception as error:                          # noqa: BLE001
        unreal.log_error("level creation failed: {0}".format(error))


run()
