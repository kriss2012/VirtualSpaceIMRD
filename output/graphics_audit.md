# Graphics & Environment Art Audit (Phase 1)

Date: 2026-10-16  
Engine: Blender 5.2.2 LTS (`BLENDER_EEVEE` / EEVEE Next)  
Backup Created: `backup/graphics_overhaul_start_2026-10-16/` (preserving `backup/pre_upgrade_2026-10-16/` and `backup/phase2_start_2026-10-16/`)

---

## 1. Current State Assessment

### A. Material System & Textures
* **Flat Untextured Shaders:** All 24 materials currently created in `01_build_campus.py` and `03_npc_interactions.py` are pure uniform diffuse colors with flat roughness/metallic scalar values (e.g., `Mat_WallExt` is solid RGB [0.92, 0.89, 0.82] with roughness 0.7; `Mat_Asphalt` is solid RGB [0.15, 0.16, 0.17] with roughness 0.7).
* **No PBR Texture Nodes:** There are zero texture coordinates, zero noise/grain patterns, zero bump/normal nodes, and zero micro-surface variation.
* **Glass Shading Defect:** `Mat_Glass` is set to metallic 0.2, roughness 0.1, base color (0.3, 0.5, 0.7) with **0.0 transmission** and no refraction/IOR. Windows appear as opaque flat blue plastic sheets rather than architectural glazing.
* **External Textures:** No external image maps (PNG/JPG/EXR) exist in the repository. Procedural PBR shaders using object/generated coordinates, noise, Voronoi, color ramps, and bump mapping must be constructed cleanly without external file dependencies.

### B. World, Lighting & Atmosphere
* **World Shading:** Default uniform gray ambient lighting (`World` with flat background). No physical sky model or atmospheric depth.
* **Direct Lighting:** Two static `SUN` lights (`Sun_Daylight` at 4.5 energy and `Sky_Fill` at 1.8 energy) without physical angular diameter or soft contact shadows.
* **EEVEE Next Capabilities Underutilized:**
  * `use_raytracing` is disabled (`False`). Screen-space reflections, ambient occlusion, and raytraced reflections are completely off.
  * `fast_gi_method` is enabled but with default low bias and no raytraced specular reflections.
  * Color management is AgX with default look ("None") and flat exposure.

### C. Architectural & Surface Detail
* **Plaster & Trim:** Walls lack subtle plaster stippling, edge wear, and vertical tone gradient (ground contact dampness).
* **Concrete & Slabs:** Plinths, slabs, and stairs lack aggregate grain, joint lines, or surface imperfections.
* **Road & Walkways:** Roads lack asphalt aggregate, micro-roughness, oil sheen, and road markings lack subtle physical thickness/wear.
* **Vegetation:** Foliage materials use flat uniform green with no translucency or leaf cluster variation.
* **Wood & Metals:** Furniture and railings lack subtle wood grain or brushed metal micro-anisotropy.

---

## 2. Implementation Plan

* **Milestone 1 (Library Foundation):** Create `scripts/materials_pbr.py` providing a centralized procedural PBR material library using Blender 5.x Principled BSDF nodes:
  * Plaster (base color micro-noise, subtle bump, roughness map).
  * Architectural concrete (fine aggregate, subtle surface pits).
  * Road asphalt & paving stone (procedural aggregate, subtle wearing).
  * Architectural glass (translucent transmission ~0.90, IOR 1.52, slight tint, low roughness, reflection-ready).
  * Weathered metals (smooth coated, dark matte, brushed stainless steel).
  * Natural wood & classroom materials (directional grain, subtle gloss).
  * Foliage & ground organic shaders.
* **Milestone 2 (Integration & Lighting):**
  * Hook PBR material builders into `01_build_campus.py` without modifying gameplay identifiers or collection hierarchy.
  * Enable EEVEE Next raytracing (`eevee.use_raytracing = True`, trace max roughness 0.65).
  * Add a realistic procedural Nishita Sky texture node setup with sun disc matching the primary sun lamp.
* **Milestone 3 (Verification & Render Check):**
  * Run automated geometry & material tests.
  * Render updated camera previews (`geometry_preview_facade.png`, `geometry_preview_overview.png`, etc.) using EEVEE Next to visually verify the upgrade.
