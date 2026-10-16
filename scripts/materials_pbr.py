"""
materials_pbr.py
================
Centralized, reusable procedural PBR material library for RCPET IMRD campus.
Designed for Blender 5.2.2 LTS (EEVEE Next & Cycles).

Key principles:
- Fully procedural (zero missing external image file dependencies).
- Real physically based shader values (Principled BSDF v2 in Blender 5.x).
- Subtle, calibrated noise & bump scales (no cartoonish or exaggerated grain).
- Translucent, reflection-ready architectural glazing (IOR 1.52, transmission).
- Accurate metallic vs non-metallic separation (concrete/plaster/wood are 0.0 metallic).
- Reusable functions with deterministic names so scene rebuilds remain idempotent.
"""

import bpy
import math


def _get_or_create_material(name):
    """Retrieve existing material by name or create a fresh one."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    if not mat.node_tree:
        # In Blender 5.x, newly created materials get node_tree automatically,
        # but if missing, use_nodes ensures it exists.
        mat.use_nodes = True
    return mat


def _clean_node_tree(mat):
    """Clear all existing nodes in material and return (nodes, links)."""
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    return nodes, links


def _get_bsdf_input(bsdf, *candidate_names):
    """Find input socket on Principled BSDF by prioritized candidate names."""
    for cand in candidate_names:
        if cand in bsdf.inputs:
            return bsdf.inputs[cand]
    return None


def create_plaster_material(name="Mat_WallExt", base_color=(0.48, 0.45, 0.39),
                            accent_color=(0.38, 0.35, 0.30), roughness=0.68, bump_strength=0.06):
    """
    Subtle architectural exterior/interior wall plaster with micro-stippling
    and realistic non-uniform surface roughness. Calibrated linear PBR albedo.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    # Texture Coordinates & Mapping
    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    mapping.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    # Fine Noise for micro-stipple
    noise_fine = nodes.new("ShaderNodeTexNoise")
    noise_fine.location = (-400, 100)
    noise_fine.inputs["Scale"].default_value = 45.0
    noise_fine.inputs["Detail"].default_value = 4.0
    noise_fine.inputs["Roughness"].default_value = 0.6
    links.new(mapping.outputs["Vector"], noise_fine.inputs["Vector"])

    # Color Ramp for subtle tone modulation
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 100)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (*accent_color[:3], 1.0)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (*base_color[:3], 1.0)
    links.new(noise_fine.outputs["Fac"], ramp.inputs["Fac"])

    # Bump node for tactile plaster texture
    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -150)
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.015
    links.new(noise_fine.outputs["Fac"], bump.inputs["Height"])

    # Principled BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_concrete_material(name="Mat_Paving", base_color=(0.32, 0.31, 0.29),
                             roughness=0.72, bump_strength=0.10):
    """
    Architectural concrete with aggregate grain, subtle pitting, and mineral variation.
    Used for plinths, slabs, paved plaza, and stair surfaces.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    # Aggregate noise
    noise_agg = nodes.new("ShaderNodeTexNoise")
    noise_agg.location = (-400, 120)
    noise_agg.inputs["Scale"].default_value = 35.0
    noise_agg.inputs["Detail"].default_value = 6.0
    noise_agg.inputs["Roughness"].default_value = 0.65
    links.new(mapping.outputs["Vector"], noise_agg.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 100)
    c_dark = [max(0.0, c * 0.85) for c in base_color[:3]]
    c_light = [min(1.0, c * 1.15) for c in base_color[:3]]
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (*c_dark, 1.0)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*c_light, 1.0)
    links.new(noise_agg.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -150)
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.02
    links.new(noise_agg.outputs["Fac"], bump.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_asphalt_material(name="Mat_Asphalt", base_color=(0.04, 0.045, 0.05),
                            roughness=0.76, bump_strength=0.14):
    """
    Road asphalt with tar binder, fine gravel aggregate, and realistic micro-roughness.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    # High frequency aggregate noise
    noise_agg = nodes.new("ShaderNodeTexNoise")
    noise_agg.location = (-400, 100)
    noise_agg.inputs["Scale"].default_value = 75.0
    noise_agg.inputs["Detail"].default_value = 6.0
    noise_agg.inputs["Roughness"].default_value = 0.7
    links.new(mapping.outputs["Vector"], noise_agg.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 100)
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.025, 0.028, 0.03, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.065, 0.07, 0.075, 1.0)
    links.new(noise_agg.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -150)
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.015
    links.new(noise_agg.outputs["Fac"], bump.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_glass_material(name="Mat_Glass", tint=(0.04, 0.07, 0.10),
                          roughness=0.03, transmission=0.85, ior=1.52):
    """
    Architectural glazing with physical transmission, IOR 1.52, and clear reflections.
    Configured for responsive viewport viewing in EEVEE Next and clean Cycles refraction.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)

    # Base Color & Tint (dark dielectric for deep exterior glass appearance)
    c_sock = _get_bsdf_input(bsdf, "Base Color")
    if c_sock:
        c_sock.default_value = (*tint[:3], 1.0)

    # Roughness
    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness

    # Transmission Weight (Blender 4.x/5.x)
    t_sock = _get_bsdf_input(bsdf, "Transmission Weight", "Transmission")
    if t_sock:
        t_sock.default_value = transmission

    # IOR
    ior_sock = _get_bsdf_input(bsdf, "IOR")
    if ior_sock:
        ior_sock.default_value = ior

    # Metallic is strictly 0 for dielectric glass
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    if hasattr(mat, "use_raytrace_refraction"):
        mat.use_raytrace_refraction = True
    if hasattr(mat, "use_transparent_shadow"):
        mat.use_transparent_shadow = True
    if hasattr(mat, "refraction_depth"):
        mat.refraction_depth = 0.08

    mat.diffuse_color = (0.1, 0.2, 0.3, 0.4)
    return mat


def create_metal_material(name="Mat_MetalDark", base_color=(0.14, 0.14, 0.15),
                          roughness=0.32, metallic=0.90, bump_strength=0.03):
    """
    Painted or brushed metal for window frames, railings, canopy columns, and lamp posts.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 80.0
    noise.inputs["Detail"].default_value = 3.0
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -100)
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.005
    links.new(noise.outputs["Fac"], bump.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    c_sock = _get_bsdf_input(bsdf, "Base Color")
    if c_sock:
        c_sock.default_value = (*base_color[:3], 1.0)
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = metallic
    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_wood_material(name="Mat_Wood", base_color=(0.42, 0.25, 0.12),
                         roughness=0.45, bump_strength=0.08):
    """
    Natural wood for plaza benches, interior desks, reception counters, and doors.
    Features directional grain and subtle warm color variation.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    # Stretch along Z or Y for longitudinal grain
    mapping.inputs["Scale"].default_value = (15.0, 1.5, 1.5)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 100)
    noise.inputs["Scale"].default_value = 18.0
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.55
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 100)
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.32, 0.18, 0.08, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.50, 0.31, 0.16, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -150)
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.01
    links.new(noise.outputs["Fac"], bump.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_foliage_material(name="Mat_Leaves", base_color=(0.14, 0.38, 0.12),
                            roughness=0.60):
    """
    Subtle organic leaf material with multi-tone green scatter and natural reflectance.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 12.0
    noise.inputs["Detail"].default_value = 3.0
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 0)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.09, 0.28, 0.08, 1.0)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.19, 0.44, 0.15, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_paver_tiles_material(name="Mat_PaverTiles", scale=4.0, roughness=0.72):
    """
    Interlocking exterior concrete paver slabs with mortar joints, stone aggregate,
    and individual tile bevel/depth. Ideal for educational institute plazas and walkways.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])

    # Brick node for individual paver blocks
    brick = nodes.new("ShaderNodeTexBrick")
    brick.location = (-350, 100)
    brick.inputs["Brick Width"].default_value = 0.50
    brick.inputs["Row Height"].default_value = 0.25
    brick.inputs["Mortar Size"].default_value = 0.022
    brick.inputs["Mortar Smooth"].default_value = 0.12
    brick.inputs["Bias"].default_value = 0.05
    brick.inputs["Color1"].default_value = (0.23, 0.21, 0.19, 1.0)
    brick.inputs["Color2"].default_value = (0.28, 0.25, 0.22, 1.0)
    brick.inputs["Mortar"].default_value = (0.07, 0.07, 0.065, 1.0)
    links.new(mapping.outputs["Vector"], brick.inputs["Vector"])

    # Fine aggregate noise
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-350, -150)
    noise.inputs["Scale"].default_value = 40.0
    noise.inputs["Detail"].default_value = 4.0
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])

    # Mortar joint recessed bump
    bump_mortar = nodes.new("ShaderNodeBump")
    bump_mortar.location = (-100, -100)
    bump_mortar.inputs["Strength"].default_value = 0.35
    bump_mortar.inputs["Distance"].default_value = 0.025
    links.new(brick.outputs["Factor"], bump_mortar.inputs["Height"])

    bump_grain = nodes.new("ShaderNodeBump")
    bump_grain.location = (100, -100)
    bump_grain.inputs["Strength"].default_value = 0.08
    bump_grain.inputs["Distance"].default_value = 0.01
    links.new(bump_mortar.outputs["Normal"], bump_grain.inputs["Normal"])
    links.new(noise.outputs["Fac"], bump_grain.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    links.new(brick.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump_grain.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (550, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (0.25, 0.23, 0.21, 1.0)
    return mat


def create_soil_material(name="Mat_Soil", base_color=(0.040, 0.028, 0.018), roughness=0.94):
    """
    Rich loamy garden soil and tree base surround with coarse crumb texture.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-600, 0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 24.0
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.75
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 50)
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[0].color = (0.025, 0.018, 0.012, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.055, 0.040, 0.025, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -150)
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.02
    links.new(noise.outputs["Fac"], bump.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def create_flowering_shrub_material(name="Mat_FlowerShrub", roughness=0.68):
    """
    Dense ornamental shrub foliage interspersed with bougainvillea / red floral blossoms.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-700, 0)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-450, 0)
    noise.inputs["Scale"].default_value = 16.0
    noise.inputs["Detail"].default_value = 4.0
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 50)
    # Leaf tones
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[0].color = (0.022, 0.065, 0.016, 1.0)
    ramp.color_ramp.elements[1].position = 0.65
    ramp.color_ramp.elements[1].color = (0.052, 0.135, 0.030, 1.0)
    # Magenta bougainvillea blossom accents
    el_flower = ramp.color_ramp.elements.new(0.85)
    el_flower.color = (0.42, 0.05, 0.16, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (0.12, 0.10, 0.08, 1.0)
    return mat


def create_grass_material(name="Mat_Grass", roughness=0.92):
    """
    Calibrated natural lawn grass ground surface with soil undertones,
    fine micro-texture, and realistic outdoor vegetative albedo.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-850, 0)
    noise_macro = nodes.new("ShaderNodeTexNoise")
    noise_macro.location = (-650, 100)
    noise_macro.inputs["Scale"].default_value = 2.2
    noise_macro.inputs["Detail"].default_value = 3.0
    links.new(tex_coord.outputs["Object"], noise_macro.inputs["Vector"])

    noise_micro = nodes.new("ShaderNodeTexNoise")
    noise_micro.location = (-650, -100)
    noise_micro.inputs["Scale"].default_value = 45.0
    noise_micro.inputs["Detail"].default_value = 4.0
    links.new(tex_coord.outputs["Object"], noise_micro.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-250, 50)
    # Calibrated realistic linear albedo values for grass (0.03 - 0.15)
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[0].color = (0.045, 0.038, 0.022, 1.0) # warm soil/thatch
    ramp.color_ramp.elements[1].position = 0.42
    ramp.color_ramp.elements[1].color = (0.024, 0.068, 0.018, 1.0) # deep lawn turf
    el_mid = ramp.color_ramp.elements.new(0.72)
    el_mid.color = (0.045, 0.125, 0.028, 1.0)                     # healthy rich grass
    el_high = ramp.color_ramp.elements.new(0.92)
    el_high.color = (0.068, 0.155, 0.038, 1.0)                    # sunlit tip

    links.new(noise_macro.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-250, -150)
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.02
    links.new(noise_micro.outputs["Fac"], bump.inputs["Height"])

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    links.new(ramp.outputs["Color"], _get_bsdf_input(bsdf, "Base Color"))
    links.new(bump.outputs["Normal"], _get_bsdf_input(bsdf, "Normal"))

    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (0.045, 0.12, 0.03, 1.0)
    return mat


def create_lamp_glow_material(name="Mat_LampGlow", color=(1.0, 0.94, 0.75), strength=8.0):
    """Warm street lamp light fixture emitter with physically pleasant glow."""
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    ec_sock = _get_bsdf_input(bsdf, "Emission Color", "Emission")
    if ec_sock:
        ec_sock.default_value = (*color[:3], 1.0)
    es_sock = _get_bsdf_input(bsdf, "Emission Strength")
    if es_sock:
        es_sock.default_value = strength
    c_sock = _get_bsdf_input(bsdf, "Base Color")
    if c_sock:
        c_sock.default_value = (*color[:3], 1.0)

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*color[:3], 1.0)
    return mat


def create_car_paint_material(name, color=(0.85, 0.12, 0.12)):
    """Automotive metallic car paint with reflective clearcoat layer."""
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    c_sock = _get_bsdf_input(bsdf, "Base Color")
    if c_sock:
        c_sock.default_value = (*color[:3], 1.0)
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.82
    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = 0.25
    cw_sock = _get_bsdf_input(bsdf, "Coat Weight", "Coat")
    if cw_sock:
        cw_sock.default_value = 1.0
    cr_sock = _get_bsdf_input(bsdf, "Coat Roughness")
    if cr_sock:
        cr_sock.default_value = 0.04

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    mat.diffuse_color = (*color[:3], 1.0)
    return mat


def create_car_glass_material(name="Mat_CarGlass"):
    """Dark tinted automotive glazing."""
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    c_sock = _get_bsdf_input(bsdf, "Base Color")
    if c_sock:
        c_sock.default_value = (0.02, 0.03, 0.04, 1.0)
    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = 0.06
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.1
    t_sock = _get_bsdf_input(bsdf, "Transmission Weight", "Transmission")
    if t_sock:
        t_sock.default_value = 0.35

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    mat.diffuse_color = (0.04, 0.06, 0.08, 0.8)
    return mat


def create_ceiling_material(name="Mat_Ceiling", base_color=(0.74, 0.72, 0.68), roughness=0.82):
    """Clean off-white architectural plaster for interior ceilings and slab undersides."""
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    c_sock = _get_bsdf_input(bsdf, "Base Color")
    if c_sock:
        c_sock.default_value = (*base_color[:3], 1.0)
    r_sock = _get_bsdf_input(bsdf, "Roughness")
    if r_sock:
        r_sock.default_value = roughness
    m_sock = _get_bsdf_input(bsdf, "Metallic")
    if m_sock:
        m_sock.default_value = 0.0

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    mat.diffuse_color = (*base_color[:3], 1.0)
    return mat


def build_full_pbr_palette():
    """Builds and returns the complete dictionary of PBR materials for IMRD campus."""
    palette = {}
    palette["grass"] = create_grass_material("Mat_Grass")
    palette["asphalt"] = create_asphalt_material("Mat_Asphalt", base_color=(0.032, 0.035, 0.038), roughness=0.74, bump_strength=0.14)
    palette["road_lines"] = create_concrete_material("Mat_RoadLines", base_color=(0.82, 0.68, 0.08), roughness=0.45, bump_strength=0.04)
    palette["paving"] = create_paver_tiles_material("Mat_Paving", scale=4.0, roughness=0.70)
    palette["curb"] = create_concrete_material("Mat_Curb", base_color=(0.28, 0.27, 0.25), roughness=0.62, bump_strength=0.06)
    palette["soil"] = create_soil_material("Mat_Soil", base_color=(0.040, 0.028, 0.018), roughness=0.94)
    palette["parking"] = create_asphalt_material("Mat_Parking", base_color=(0.045, 0.050, 0.055), roughness=0.75, bump_strength=0.12)
    palette["park_lines"] = create_concrete_material("Mat_ParkLines", base_color=(0.75, 0.75, 0.75), roughness=0.40, bump_strength=0.04)

    # Architecture
    palette["wall_ext"] = create_plaster_material("Mat_WallExt", base_color=(0.48, 0.45, 0.39), accent_color=(0.38, 0.35, 0.30), roughness=0.68)
    palette["wall_trim"] = create_plaster_material("Mat_WallTrim", base_color=(0.40, 0.16, 0.06), accent_color=(0.30, 0.11, 0.04), roughness=0.55)
    palette["wall_int"] = create_plaster_material("Mat_WallInt", base_color=(0.60, 0.58, 0.54), accent_color=(0.50, 0.48, 0.44), roughness=0.75, bump_strength=0.03)
    palette["floor_tile"] = create_concrete_material("Mat_FloorTile", base_color=(0.42, 0.40, 0.37), roughness=0.28, bump_strength=0.03)
    palette["ceiling"] = create_ceiling_material("Mat_Ceiling")
    palette["glass"] = create_glass_material("Mat_Glass")
    palette["car_glass"] = create_car_glass_material("Mat_CarGlass")

    # Props & Furniture
    palette["wood"] = create_wood_material("Mat_Wood", base_color=(0.18, 0.10, 0.04))
    palette["door"] = create_wood_material("Mat_InteractiveDoor", base_color=(0.20, 0.11, 0.05), roughness=0.42)
    palette["metal_dark"] = create_metal_material("Mat_MetalDark", base_color=(0.04, 0.04, 0.045), roughness=0.32, metallic=0.88)
    palette["board"] = create_metal_material("Mat_Board", base_color=(0.03, 0.10, 0.05), roughness=0.35, metallic=0.0)
    palette["lamp_glow"] = create_lamp_glow_material("Mat_LampGlow", color=(1.0, 0.94, 0.75), strength=8.0)

    # Vegetation
    palette["leaves"] = create_foliage_material("Mat_Leaves", base_color=(0.042, 0.125, 0.026), roughness=0.62)
    palette["flower_shrub"] = create_flowering_shrub_material("Mat_FlowerShrub", roughness=0.68)
    palette["trunk"] = create_wood_material("Mat_Trunk", base_color=(0.12, 0.08, 0.04), roughness=0.85, bump_strength=0.20)

    return palette
