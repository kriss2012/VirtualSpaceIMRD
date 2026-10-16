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


def create_plaster_material(name="Mat_WallExt", base_color=(0.92, 0.89, 0.82),
                            accent_color=(0.88, 0.84, 0.77), roughness=0.68, bump_strength=0.06):
    """
    Subtle architectural exterior/interior wall plaster with micro-stippling
    and realistic non-uniform surface roughness.
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


def create_concrete_material(name="Mat_Paving", base_color=(0.76, 0.74, 0.68),
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

    # Macro tone variation (Voronoi/noise blend)
    noise_macro = nodes.new("ShaderNodeTexNoise")
    noise_macro.location = (-400, -100)
    noise_macro.inputs["Scale"].default_value = 4.0
    noise_macro.inputs["Detail"].default_value = 2.0
    links.new(mapping.outputs["Vector"], noise_macro.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 100)
    c_dark = [max(0.0, c * 0.88) for c in base_color[:3]]
    c_light = [min(1.0, c * 1.06) for c in base_color[:3]]
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


def create_asphalt_material(name="Mat_Asphalt", base_color=(0.14, 0.15, 0.16),
                            roughness=0.78, bump_strength=0.14):
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
    ramp.color_ramp.elements[0].color = (0.11, 0.12, 0.13, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.19, 0.20, 0.21, 1.0)
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


def create_glass_material(name="Mat_Glass", tint=(0.88, 0.94, 0.98),
                          roughness=0.03, transmission=0.88, ior=1.52):
    """
    Architectural glazing with physical transmission, IOR 1.52, and clear reflections.
    Configured for responsive viewport viewing in EEVEE Next and clean Cycles refraction.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)

    # Base Color & Tint
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

    mat.diffuse_color = (0.3, 0.5, 0.7, 0.4)
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


def create_grass_material(name="Mat_Grass", base_color=(0.16, 0.36, 0.14),
                          roughness=0.85):
    """
    Lawn grass ground surface with natural patchiness, soil undertones, and high roughness.
    """
    mat = _get_or_create_material(name)
    nodes, links = _clean_node_tree(mat)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    noise_macro = nodes.new("ShaderNodeTexNoise")
    noise_macro.location = (-600, 100)
    noise_macro.inputs["Scale"].default_value = 3.5
    noise_macro.inputs["Detail"].default_value = 3.0
    links.new(tex_coord.outputs["Object"], noise_macro.inputs["Vector"])

    noise_micro = nodes.new("ShaderNodeTexNoise")
    noise_micro.location = (-600, -100)
    noise_micro.inputs["Scale"].default_value = 35.0
    noise_micro.inputs["Detail"].default_value = 4.0
    links.new(tex_coord.outputs["Object"], noise_micro.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 50)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.12, 0.28, 0.10, 1.0) # deeper green
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (0.22, 0.42, 0.17, 1.0) # healthy warm grass
    links.new(noise_macro.outputs["Fac"], ramp.inputs["Fac"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-200, -150)
    bump.inputs["Strength"].default_value = 0.12
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

    mat.diffuse_color = (*base_color[:3], 1.0)
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


def build_full_pbr_palette():
    """Builds and returns the complete dictionary of PBR materials for IMRD campus."""
    palette = {}
    palette["grass"] = create_grass_material("Mat_Grass")
    palette["asphalt"] = create_asphalt_material("Mat_Asphalt", base_color=(0.14, 0.15, 0.16))
    palette["road_lines"] = create_concrete_material("Mat_RoadLines", base_color=(0.95, 0.85, 0.20), roughness=0.45, bump_strength=0.04)
    palette["paving"] = create_concrete_material("Mat_Paving", base_color=(0.76, 0.74, 0.68), roughness=0.68, bump_strength=0.08)
    palette["parking"] = create_asphalt_material("Mat_Parking", base_color=(0.20, 0.21, 0.23), roughness=0.74, bump_strength=0.12)
    palette["park_lines"] = create_concrete_material("Mat_ParkLines", base_color=(0.90, 0.90, 0.90), roughness=0.40, bump_strength=0.04)

    # Architecture
    palette["wall_ext"] = create_plaster_material("Mat_WallExt", base_color=(0.92, 0.89, 0.82), accent_color=(0.86, 0.82, 0.75), roughness=0.68)
    palette["wall_trim"] = create_plaster_material("Mat_WallTrim", base_color=(0.78, 0.42, 0.18), accent_color=(0.72, 0.38, 0.15), roughness=0.55)
    palette["wall_int"] = create_plaster_material("Mat_WallInt", base_color=(0.96, 0.95, 0.92), accent_color=(0.91, 0.90, 0.87), roughness=0.75, bump_strength=0.03)
    palette["floor_tile"] = create_concrete_material("Mat_FloorTile", base_color=(0.84, 0.82, 0.78), roughness=0.38, bump_strength=0.04)
    palette["glass"] = create_glass_material("Mat_Glass")

    # Props & Furniture
    palette["wood"] = create_wood_material("Mat_Wood", base_color=(0.42, 0.25, 0.12))
    palette["door"] = create_wood_material("Mat_InteractiveDoor", base_color=(0.46, 0.28, 0.15), roughness=0.42)
    palette["metal_dark"] = create_metal_material("Mat_MetalDark", base_color=(0.14, 0.14, 0.15), roughness=0.32, metallic=0.88)
    palette["board"] = create_metal_material("Mat_Board", base_color=(0.06, 0.22, 0.10), roughness=0.35, metallic=0.0)
    palette["lamp_glow"] = create_lamp_glow_material("Mat_LampGlow", color=(1.0, 0.94, 0.75), strength=8.0)

    # Vegetation
    palette["leaves"] = create_foliage_material("Mat_Leaves")
    palette["trunk"] = create_wood_material("Mat_Trunk", base_color=(0.30, 0.20, 0.11), roughness=0.85, bump_strength=0.20)

    return palette
