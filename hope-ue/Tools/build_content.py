"""
Generates the project's material assets and an empty street level.

Run from inside the editor:  Window > Developer Tools > Output Log,
then in the Cmd box switch the dropdown to "Python" and enter:

    exec(open(r"<project>/Tools/build_content.py").read())

This step is OPTIONAL. Without it the game still runs — HopeBlocks::MaterialFor
falls back to a tinted instance of the engine's basic shape material, so the
street is correctly coloured but flat. Running it gives every surface a
noise-driven base colour and roughness break-up, which is what stops the long
facades from reading as untextured boxes.

The parameter names created here are exactly the ones the C++ sets:
BaseColorTint, Roughness, Metallic, EmissiveTint, EmissiveStrength.

This is not the photorealism step. See README.md — real fidelity comes from
replacing these with scanned Megascans materials, which cannot be redistributed
in this repository.
"""

import unreal

MATERIAL_DIR = "/Game/Materials"
MAP_DIR = "/Game/Maps"

# key -> (noise scale in cm, how strongly the noise breaks up the base colour)
SURFACES = {
    "Asphalt":  (60.0, 0.35),
    "Sidewalk": (45.0, 0.30),
    "Kerb":     (40.0, 0.22),
    "Dirt":     (120.0, 0.45),
    "Stucco":   (35.0, 0.28),
    "Brick":    (18.0, 0.40),
    "Shutter":  (12.0, 0.18),
    "Sign":     (25.0, 0.15),
    "Awning":   (30.0, 0.25),
    "Glass":    (80.0, 0.10),
    "Metal":    (22.0, 0.20),
    "Leather":  (14.0, 0.30),
    "Fabric":   (10.0, 0.26),
    "Skin":     (8.0, 0.12),
    "Patch":    (10.0, 0.15),
    "Shadow":   (50.0, 0.05),
}

mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def expr(material, cls, x, y, **props):
    node = mel.create_material_expression(material, cls, x, y)
    for key, value in props.items():
        node.set_editor_property(key, value)
    return node


def build_material(key, noise_scale, noise_strength):
    name = "M_Hope_{0}".format(key)
    path = "{0}/{1}".format(MATERIAL_DIR, name)

    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)

    material = tools.create_asset(name, MATERIAL_DIR, unreal.Material,
                                  unreal.MaterialFactoryNew())

    # Base colour: a tint parameter multiplied by low-frequency noise, so a
    # 200 m facade never repeats. This is the same trick the WebGL build used
    # with per-vertex mottling, done per-pixel instead.
    tint = expr(material, unreal.MaterialExpressionVectorParameter, -900, -200,
                parameter_name="BaseColorTint",
                default_value=unreal.LinearColor(0.5, 0.5, 0.5, 1.0))

    noise = expr(material, unreal.MaterialExpressionNoise, -900, 60,
                 scale=1.0 / max(noise_scale, 0.001),
                 levels=4,
                 output_min=1.0 - noise_strength,
                 output_max=1.0 + noise_strength)

    tinted = expr(material, unreal.MaterialExpressionMultiply, -560, -120)
    mel.connect_material_expressions(tint, "", tinted, "A")
    mel.connect_material_expressions(noise, "", tinted, "B")
    mel.connect_material_property(tinted, "", unreal.MaterialProperty.MP_BASE_COLOR)

    # Roughness: parameter, broken up by the same noise so highlights vary.
    rough = expr(material, unreal.MaterialExpressionScalarParameter, -900, 260,
                 parameter_name="Roughness", default_value=0.8)
    rough_mul = expr(material, unreal.MaterialExpressionMultiply, -560, 260)
    mel.connect_material_expressions(rough, "", rough_mul, "A")
    mel.connect_material_expressions(noise, "", rough_mul, "B")
    mel.connect_material_property(rough_mul, "", unreal.MaterialProperty.MP_ROUGHNESS)

    metal = expr(material, unreal.MaterialExpressionScalarParameter, -560, 400,
                 parameter_name="Metallic", default_value=0.0)
    mel.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)

    # Emissive, driven at runtime for the shadows' hit flash.
    emissive_tint = expr(material, unreal.MaterialExpressionVectorParameter, -900, 540,
                         parameter_name="EmissiveTint",
                         default_value=unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    emissive_str = expr(material, unreal.MaterialExpressionScalarParameter, -900, 700,
                        parameter_name="EmissiveStrength", default_value=0.0)
    emissive = expr(material, unreal.MaterialExpressionMultiply, -560, 600)
    mel.connect_material_expressions(emissive_tint, "", emissive, "A")
    mel.connect_material_expressions(emissive_str, "", emissive, "B")
    mel.connect_material_property(emissive, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)

    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path)
    return path


def build_level():
    """An empty level. The street actor builds itself into it at BeginPlay."""
    path = "{0}/Street".format(MAP_DIR)
    subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    subsystem.new_level(path)
    subsystem.save_current_level()
    return path


def run():
    made = []
    for key, (scale, strength) in SURFACES.items():
        try:
            made.append(build_material(key, scale, strength))
        except Exception as error:                      # noqa: BLE001
            unreal.log_error("M_Hope_{0} failed: {1}".format(key, error))

    unreal.log("built {0}/{1} materials".format(len(made), len(SURFACES)))

    try:
        unreal.log("level: {0}".format(build_level()))
    except Exception as error:                          # noqa: BLE001
        unreal.log_error("level creation failed: {0}".format(error))


run()
