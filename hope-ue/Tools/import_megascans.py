"""
Imports downloaded Megascans / Fab surface sets and wires them into the game.

This is the photorealism step. Everything else in the project sets up a
renderer capable of showing scanned surfaces; this is what actually puts them
on the street.

Usage
-----
1. In the editor, open Fab (Window > Fab) and download the surfaces you want.
   Anything from the "Surfaces" category works. Download them as **source
   files** to a folder on disk, not as Unreal assets — this script handles the
   import so the texture compression settings come out right.

2. Point SOURCE_ROOT at that folder and edit ASSIGNMENTS to say which
   downloaded surface covers which of the game's materials.

3. Output Log > console dropdown "Python":

       exec(open(r"<project>/Tools/import_megascans.py").read())

Run build_content.py first — this script sets texture parameters on the
MI_Hope_* instances that one creates.

Why the textures are imported here rather than dragged in
---------------------------------------------------------
Compression settings are not cosmetic. A normal map imported as a colour
texture is stored with sRGB encoding and BC1 compression, which quantises the
very small XY deviations that make a surface look scanned rather than painted —
the map survives, the microdetail does not. Same for the packed ORD map: read
as sRGB, the roughness channel comes out gamma-curved and every surface reads
too glossy. This script sets both explicitly.
"""

import os

import unreal

# ---------------------------------------------------------------------------
# EDIT THESE TWO
# ---------------------------------------------------------------------------

# Folder holding the downloaded surfaces, one subfolder per surface.
SOURCE_ROOT = r"C:/Megascans/Downloaded/surface"

# Game material key -> the subfolder name under SOURCE_ROOT.
# Keys are the ones in HopeStreet.cpp; anything left out keeps its flat tint.
ASSIGNMENTS = {
    "Asphalt":  "damaged_asphalt_uh4ndfhr",
    "Sidewalk": "concrete_pavement_vlxiaftt",
    "Kerb":     "concrete_pavement_vlxiaftt",
    "Dirt":     "dry_dirt_ground_ujwxbb2fa",
    "Stucco":   "damaged_plaster_wall_tfxobcyr",
    "Brick":    "old_brick_wall_ufwqcgtfa",
    "Metal":    "rusted_painted_metal_vjzjbhtr",
}

# ---------------------------------------------------------------------------

DEST_ROOT = "/Game/Scanned"
MATERIAL_DIR = "/Game/Materials"

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

# Megascans names its maps consistently enough to match on substrings.
# Order matters: "Normal" before "NormalBump", "AO" last so it loses to ORD.
MAP_PATTERNS = {
    "BaseColorMap": ("albedo", "basecolor", "diffuse"),
    "NormalMap": ("normal",),
    "ORDMap": ("_ord", "orm", "occlusionroughnessmetallic", "roughness"),
}

TEXTURE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tga", ".exr", ".tif", ".tiff")


def find_maps(folder):
    """Returns {parameter name: absolute path} for one surface folder."""
    found = {}
    try:
        entries = sorted(os.listdir(folder))
    except OSError as error:
        unreal.log_error("cannot read {0}: {1}".format(folder, error))
        return found

    for entry in entries:
        lower = entry.lower()
        if not lower.endswith(TEXTURE_EXTENSIONS):
            continue
        # Megascans ships several resolutions; skip the preview thumbnails.
        if "preview" in lower or "thumb" in lower:
            continue
        for param, patterns in MAP_PATTERNS.items():
            if param in found:
                continue
            if any(p in lower for p in patterns):
                found[param] = os.path.join(folder, entry)
                break
    return found


def import_texture(source_path, destination):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", source_path)
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)

    tools.import_asset_tasks([task])
    paths = task.get_editor_property("imported_object_paths")
    if not paths:
        return None
    return unreal.load_asset(paths[0])


def configure_texture(texture, param):
    """The whole reason this script exists — see the module docstring."""
    if param == "NormalMap":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
    elif param == "ORDMap":
        texture.set_editor_property("srgb", False)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    else:
        texture.set_editor_property("srgb", True)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)

    # Scanned surfaces are large and tiled; virtual texturing keeps 8K sets off
    # the resident budget. r.VirtualTextures is already on in DefaultEngine.ini.
    texture.set_editor_property("virtual_texture_streaming", True)
    eal.save_loaded_asset(texture)


def apply_surface(key, folder_name):
    folder = os.path.join(SOURCE_ROOT, folder_name)
    if not os.path.isdir(folder):
        unreal.log_warning("{0}: no such folder {1}".format(key, folder))
        return False

    instance_path = "{0}/MI_Hope_{1}".format(MATERIAL_DIR, key)
    instance = unreal.load_asset(instance_path)
    if not instance:
        unreal.log_warning(
            "{0}: {1} missing — run build_content.py first".format(key, instance_path))
        return False

    maps = find_maps(folder)
    if not maps:
        unreal.log_warning("{0}: no textures matched in {1}".format(key, folder))
        return False

    destination = "{0}/{1}".format(DEST_ROOT, key)
    applied = []
    for param, source_path in maps.items():
        texture = import_texture(source_path, destination)
        if not texture:
            unreal.log_warning("{0}: import failed for {1}".format(key, source_path))
            continue
        configure_texture(texture, param)
        mel.set_material_instance_texture_parameter_value(instance, param, texture)
        applied.append(param)

    # A scan carries its own colour. Neutralise the placeholder tint, or the
    # albedo gets multiplied down to near black.
    if "BaseColorMap" in applied:
        mel.set_material_instance_vector_parameter_value(
            instance, "BaseColorTint", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    # Same for roughness: the ORD map is the authority now.
    if "ORDMap" in applied:
        mel.set_material_instance_scalar_parameter_value(instance, "Roughness", 1.0)

    eal.save_loaded_asset(instance)
    unreal.log("{0}: {1}".format(key, ", ".join(applied)))
    return True


def run():
    if not os.path.isdir(SOURCE_ROOT):
        unreal.log_error(
            "SOURCE_ROOT does not exist: {0} — edit it at the top of this file"
            .format(SOURCE_ROOT))
        return

    done = sum(1 for key, folder in ASSIGNMENTS.items() if apply_surface(key, folder))
    unreal.log("{0}/{1} surfaces applied".format(done, len(ASSIGNMENTS)))
    if done:
        unreal.log("Press Play — the street is now on scanned surfaces.")


run()
