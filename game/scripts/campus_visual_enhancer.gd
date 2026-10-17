extends Node

# CampusVisualEnhancer
# Automatically configures rich, realistic PBR materials and environmental lighting
# across all imported campus geometry, vegetation, roads, buildings, and character models.

func _ready() -> void:
	enhance_campus_environment()
	apply_all_campus_materials()
	calibrate_stair_railings()
	print("[VisualEnhancer] Realistic PBR materials & lighting successfully calibrated.")


func enhance_campus_environment(target_root: Node = null) -> void:
	var root = target_root if target_root != null else (get_parent() if get_parent() else self)
		
	# 1. Calibrate Directional Sunlight (Smooth soft shadows, no low-res stepping)
	var sun: DirectionalLight3D = root.find_child("DirectionalLight3D", true, false) as DirectionalLight3D
	if sun:
		sun.light_color = Color(1.0, 0.97, 0.92) # Warm sunny daylight
		sun.light_energy = 1.15
		sun.shadow_enabled = true
		sun.shadow_bias = 0.02
		sun.shadow_normal_bias = 2.0
		sun.shadow_blur = 1.8
		sun.directional_shadow_max_distance = 120.0
		sun.directional_shadow_split_1 = 0.12
		sun.directional_shadow_split_2 = 0.28
		sun.directional_shadow_split_3 = 0.60
		sun.directional_shadow_blend_splits = true
		
	# 2. Calibrate World Environment & Sky
	var world_env: WorldEnvironment = root.find_child("WorldEnvironment", true, false) as WorldEnvironment
	if world_env and world_env.environment:
		var env = world_env.environment
		env.background_mode = Environment.BG_SKY
		
		# Procedural Sky setup - warm neutral ground fill prevents dark green ceiling discoloration
		var sky_mat = ProceduralSkyMaterial.new()
		sky_mat.sky_top_color = Color(0.25, 0.50, 0.86) # Rich azure blue sky
		sky_mat.sky_horizon_color = Color(0.80, 0.85, 0.92) # Atmospheric haze
		sky_mat.ground_bottom_color = Color(0.70, 0.72, 0.76) # Clean neutral ambient fill for ceilings
		sky_mat.ground_horizon_color = Color(0.78, 0.80, 0.84)
		sky_mat.sun_angle_max = 28.0
		
		var sky = Sky.new()
		sky.sky_material = sky_mat
		env.sky = sky
		
		# Calibrated Ambient Light (eliminates dark green tint & chalky white blowout)
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.ambient_light_color = Color(0.75, 0.78, 0.85)
		env.ambient_light_energy = 0.40
		
		# Tonemapping & Post-processing
		env.tonemap_mode = Environment.TONE_MAPPER_ACES
		env.tonemap_exposure = 1.05
		env.tonemap_white = 1.0
		env.ssao_enabled = true
		env.ssao_radius = 1.2
		env.ssao_intensity = 1.5
		env.glow_enabled = true
		env.glow_intensity = 0.18
		env.glow_bloom = 0.04


func apply_all_campus_materials(target_root: Node = null) -> void:
	var root = target_root if target_root != null else (get_parent() if get_parent() else self)
		
	# Build rich PBR materials library
	var mats = build_material_library()
	
	# Apply recursively to all MeshInstance3D nodes
	apply_recursive(root, mats)


func build_material_library() -> Dictionary:
	var lib = {}
	
	# 1. Terrain & Grounds
	lib["Mat_Grass"] = create_mat(Color(0.24, 0.52, 0.16), 0.88, 0.0) # Lush green lawn
	lib["Mat_Asphalt"] = create_mat(Color(0.18, 0.19, 0.20), 0.80, 0.0) # Dark asphalt road
	lib["Mat_Curb"] = create_mat(Color(0.72, 0.72, 0.70), 0.65, 0.0) # Concrete curbs
	lib["Mat_Soil"] = create_mat(Color(0.28, 0.18, 0.12), 0.92, 0.0) # Dark rich garden soil
	lib["Mat_Paving"] = create_mat(Color(0.74, 0.65, 0.55), 0.60, 0.0) # Sandstone plaza tiles
	lib["Mat_Parking"] = create_mat(Color(0.22, 0.23, 0.24), 0.75, 0.0) # Parking surface
	lib["Mat_RoadLines"] = create_mat(Color(0.96, 0.80, 0.14), 0.45, 0.0) # Golden yellow dashes
	lib["Mat_ParkLines"] = create_mat(Color(0.95, 0.95, 0.95), 0.40, 0.0) # White parking & zebra stripes
	
	# 2. Building Architecture
	lib["Mat_WallExt"] = create_mat(Color(0.88, 0.84, 0.76), 0.75, 0.0) # Academic sandstone facade
	lib["Mat_WallInt"] = create_mat(Color(0.94, 0.92, 0.88), 0.85, 0.0) # Clean classroom plaster
	lib["Mat_WallTrim"] = create_mat(Color(0.65, 0.26, 0.16), 0.48, 0.0) # Warm terracotta architectural trim
	lib["Mat_FloorTile"] = create_mat(Color(0.86, 0.84, 0.80), 0.52, 0.0) # Matte honed marble lobby tiles (no specular blowout)
	lib["Mat_Wood"] = create_mat(Color(0.38, 0.20, 0.10), 0.45, 0.0) # Polished teak doors & window frames
	lib["Mat_Ceiling"] = create_mat(Color(0.96, 0.96, 0.96), 0.90, 0.0) # Clean white acoustic ceiling plaster
	lib["Mat_MetalDark"] = create_mat(Color(0.10, 0.10, 0.12), 0.30, 0.85) # Black iron railings & gate
	
	# Architectural Glass (reflective, translucent)
	var glass = StandardMaterial3D.new()
	glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	glass.albedo_color = Color(0.12, 0.24, 0.38, 0.60)
	glass.roughness = 0.04
	glass.metallic = 0.20
	lib["Mat_Glass"] = glass
	
	# 3. Nature & Vegetation
	lib["Mat_Leaves"] = create_mat(Color(0.18, 0.44, 0.14), 0.70, 0.0) # Rich tree canopy foliage
	lib["Mat_Trunk"] = create_mat(Color(0.30, 0.18, 0.10), 0.88, 0.0) # Cedar bark trunk
	lib["Mat_FlowerShrub"] = create_mat(Color(0.82, 0.22, 0.32), 0.60, 0.0) # Red flowering bushes
	
	# 4. Furniture & Props
	lib["Mat_Board"] = create_mat(Color(0.12, 0.24, 0.14), 0.55, 0.0) # Classic school chalkboard
	
	# Emissive Streetlamp Glow
	var lamp = StandardMaterial3D.new()
	lamp.albedo_color = Color(1.0, 0.95, 0.75)
	lamp.emission_enabled = true
	lamp.emission = Color(1.0, 0.90, 0.65)
	lamp.emission_energy_multiplier = 3.0
	lib["Mat_LampGlow"] = lamp
	
	# Cars & Bikes (Authentic reference models: Tata Nano EV, Corvette C8 Z06, Tata Punch.ev, Joy e-bike Beast, Aurore EV)
	lib["Mat_Car_NanoWhite"] = create_mat(Color(0.95, 0.95, 0.95), 0.18, 0.35) # Pure gloss white
	lib["Mat_Car_CorvetteRed"] = create_mat(Color(0.86, 0.07, 0.09), 0.15, 0.75) # Torch Red supercar metallic
	lib["Mat_Car_PunchLime"] = create_mat(Color(0.72, 0.82, 0.15), 0.20, 0.65) # Citron / Lime-Yellow EV SUV
	lib["Mat_Bike_BeastGreen"] = create_mat(Color(0.18, 0.82, 0.15), 0.18, 0.70) # Joy e-bike Beast lime green
	lib["Mat_Bike_AuroreBlue"] = create_mat(Color(0.12, 0.45, 0.78), 0.18, 0.75) # Metallic Electric Blue sports bike
	lib["Mat_Car_SedanSilver"] = create_mat(Color(0.84, 0.86, 0.88), 0.22, 0.85) # Metallic silver executive sedan
	lib["Mat_PlasticBlack"] = create_mat(Color(0.04, 0.04, 0.045), 0.65, 0.0) # Matte/satin black claddings
	lib["Mat_CarbonFiber"] = create_mat(Color(0.05, 0.05, 0.055), 0.35, 0.3) # Dark woven carbon fiber
	lib["Mat_EV_Plate"] = create_mat(Color(0.08, 0.65, 0.22), 0.35, 0.0) # Electric vehicle green number plate
	lib["Mat_TireRubber"] = create_mat(Color(0.03, 0.03, 0.035), 0.85, 0.0) # Matte tire rubber
	lib["Mat_AlloySilver"] = create_mat(Color(0.82, 0.84, 0.86), 0.25, 0.88) # Machined alloy silver wheels
	
	# Emissive Vehicle Lights
	var led_headlight = StandardMaterial3D.new()
	led_headlight.albedo_color = Color(1.0, 1.0, 1.0)
	led_headlight.emission_enabled = true
	led_headlight.emission = Color(0.95, 0.98, 1.0)
	led_headlight.emission_energy_multiplier = 2.5
	lib["Mat_Headlight_LED"] = led_headlight
	
	var led_taillight = StandardMaterial3D.new()
	led_taillight.albedo_color = Color(0.90, 0.05, 0.05)
	led_taillight.emission_enabled = true
	led_taillight.emission = Color(0.95, 0.05, 0.05)
	led_taillight.emission_energy_multiplier = 2.0
	lib["Mat_Taillight_LED"] = led_taillight
	
	# Legacy car color fallbacks
	lib["Mat_Car_0"] = lib["Mat_Car_NanoWhite"]
	lib["Mat_Car_1"] = lib["Mat_Car_CorvetteRed"]
	lib["Mat_Car_2"] = lib["Mat_Car_PunchLime"]
	lib["Mat_Car_3"] = lib["Mat_Bike_BeastGreen"]
	lib["Mat_Car_4"] = lib["Mat_Bike_AuroreBlue"]
	lib["Mat_Car_5"] = lib["Mat_Car_SedanSilver"]
	
	var car_glass = StandardMaterial3D.new()
	car_glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	car_glass.albedo_color = Color(0.08, 0.10, 0.14, 0.75)
	car_glass.roughness = 0.05
	lib["Mat_CarGlass"] = car_glass
	
	# 5. Characters (Student & Guide)
	lib["Mat_Backpack"] = create_mat(Color(0.38, 0.22, 0.12), 0.50, 0.0) # Leather backpack
	lib["Mat_StudentHair"] = create_mat(Color(0.12, 0.10, 0.08), 0.40, 0.0) # Dark styled hair
	lib["Mat_StudentSkin"] = create_mat(Color(0.85, 0.68, 0.55), 0.60, 0.0) # Realistic skin tone
	lib["Mat_StudentBlazer"] = create_mat(Color(0.10, 0.18, 0.35), 0.55, 0.0) # Navy blue IMRD blazer
	lib["Mat_StudentShirt"] = create_mat(Color(0.95, 0.95, 0.95), 0.60, 0.0) # White formal shirt
	lib["Mat_StudentTie"] = create_mat(Color(0.55, 0.08, 0.12), 0.40, 0.0) # Maroon tie
	lib["Mat_StudentPants"] = create_mat(Color(0.20, 0.22, 0.25), 0.65, 0.0) # Charcoal trousers
	lib["Mat_StudentShoes"] = create_mat(Color(0.08, 0.08, 0.08), 0.30, 0.0) # Polished black shoes
	lib["Mat_GuideJacket"] = create_mat(Color(0.25, 0.28, 0.32), 0.55, 0.0) # Prof. Sharma blazer
	
	return lib


func create_mat(albedo: Color, rough: float, metal: float) -> StandardMaterial3D:
	var m = StandardMaterial3D.new()
	m.albedo_color = albedo
	m.roughness = rough
	m.metallic = metal
	return m


func apply_recursive(node: Node, lib: Dictionary) -> void:
	if node is MeshInstance3D and node.mesh:
		var m = node.mesh
		var count = m.get_surface_count()
		for s in range(count):
			var existing_mat = m.surface_get_material(s)
			var mat_name = existing_mat.resource_name if existing_mat and existing_mat.resource_name else ""
			
			# Check direct material name match
			if lib.has(mat_name):
				node.set_surface_override_material(s, lib[mat_name])
			else:
				# Smart fallback by node/mesh naming
				var assigned = resolve_by_node_name(node.name, lib)
				if assigned:
					node.set_surface_override_material(s, assigned)
					
	for child in node.get_children():
		apply_recursive(child, lib)


func resolve_by_node_name(n: String, lib: Dictionary) -> StandardMaterial3D:
	var name_lower = n.to_lower()
	if "grass" in name_lower or "lawn" in name_lower:
		return lib["Mat_Grass"]
	elif "road" in name_lower or "asphalt" in name_lower:
		if "dash" in name_lower or "line" in name_lower:
			return lib["Mat_RoadLines"]
		elif "zebra" in name_lower:
			return lib["Mat_ParkLines"]
		return lib["Mat_Asphalt"]
	elif "curb" in name_lower:
		return lib["Mat_Curb"]
	elif "soil" in name_lower or "flowerbed" in name_lower:
		return lib["Mat_Soil"]
	elif "paving" in name_lower or "plaza" in name_lower or "walkway" in name_lower or "step" in name_lower or "plinth" in name_lower or "stair" in name_lower:
		return lib["Mat_Paving"]
	elif "door" in name_lower or "desk" in name_lower or "podium" in name_lower or "table" in name_lower:
		return lib["Mat_Wood"]
	elif "tree" in name_lower or "crown" in name_lower or "foliage" in name_lower or "leaves" in name_lower:
		return lib["Mat_Leaves"]
	elif "trunk" in name_lower or "bark" in name_lower:
		return lib["Mat_Trunk"]
	elif "parking" in name_lower:
		if "line" in name_lower:
			return lib["Mat_ParkLines"]
		return lib["Mat_Parking"]
	elif "wall" in name_lower:
		if "int" in name_lower or "class" in name_lower:
			return lib["Mat_WallInt"]
		elif "trim" in name_lower or "canopy" in name_lower or "sign" in name_lower:
			return lib["Mat_WallTrim"]
		return lib["Mat_WallExt"]
	elif "floor" in name_lower or "slab" in name_lower:
		return lib["Mat_FloorTile"]
	elif "roof" in name_lower or "ceiling" in name_lower:
		return lib["Mat_Ceiling"]
	elif "glass" in name_lower:
		return lib["Mat_Glass"]
	elif "rail" in name_lower or "gate" in name_lower or "lamp" in name_lower or "pole" in name_lower or "boundary" in name_lower:
		if "glow" in name_lower:
			return lib["Mat_LampGlow"]
		return lib["Mat_MetalDark"]
	elif "board" in name_lower:
		return lib["Mat_Board"]
	elif "torso" in name_lower or "blazer" in name_lower or "body" in name_lower:
		if "student" in name_lower or "player" in name_lower:
			return lib["Mat_StudentBlazer"]
		elif "npc" in name_lower or "guide" in name_lower:
			return lib["Mat_GuideJacket"]
	elif "leg" in name_lower or "pants" in name_lower:
		return lib["Mat_StudentPants"]
	elif "foot" in name_lower or "shoe" in name_lower:
		return lib["Mat_StudentShoes"]
	elif "head" in name_lower or "arm" in name_lower or "hand" in name_lower or "skin" in name_lower:
		return lib["Mat_StudentSkin"]
	elif "hair" in name_lower:
		return lib["Mat_StudentHair"]
	elif "backpack" in name_lower:
		return lib["Mat_Backpack"]
	return null


func calibrate_stair_railings(target_root: Node = null) -> void:
	var root = target_root if target_root != null else (get_parent() if get_parent() else self)
	
	# 1. Hide the old glitchy Blender stair rails that poke past the landing into the walkway
	var r_l = root.find_child("Rail_Stair_L", true, false)
	if r_l is Node3D:
		r_l.visible = false
	var r_r = root.find_child("Rail_Stair_R", true, false)
	if r_r is Node3D:
		r_r.visible = false
		
	# 2. Calibrate SecondFloorEnvironment void guards to extend all the way to Z = -1.10
	var g_l = root.find_child("StairVoidGuardLeft", true, false)
	if g_l is Node3D:
		g_l.position = Vector3(3.90, 4.85, -3.55)
		var h = g_l.find_child("Handrail", true, false)
		if h and h.mesh and h.mesh is BoxMesh:
			h.mesh.size = Vector3(0.06, 0.06, 4.90)
		var gl = g_l.find_child("Glass", true, false)
		if gl and gl.mesh and gl.mesh is BoxMesh:
			gl.mesh.size = Vector3(0.02, 0.90, 4.80)
		var col = g_l.find_child("CollisionShape3D", true, false)
		if col and col.shape and col.shape is BoxShape3D:
			col.shape.size = Vector3(0.18, 1.20, 4.90)
			
	var g_r = root.find_child("StairVoidGuardRight", true, false)
	if g_r is Node3D:
		g_r.position = Vector3(6.10, 4.85, -3.55)
		var h = g_r.find_child("Handrail", true, false)
		if h and h.mesh and h.mesh is BoxMesh:
			h.mesh.size = Vector3(0.06, 0.06, 4.90)
		var gl = g_r.find_child("Glass", true, false)
		if gl and gl.mesh and gl.mesh is BoxMesh:
			gl.mesh.size = Vector3(0.02, 0.90, 4.80)
		var col = g_r.find_child("CollisionShape3D", true, false)
		if col and col.shape and col.shape is BoxShape3D:
			col.shape.size = Vector3(0.18, 1.20, 4.90)

