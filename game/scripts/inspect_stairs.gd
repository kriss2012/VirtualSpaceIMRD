@tool
extends SceneTree

func _init() -> void:
	print("=== INSPECTING STAIRS & ARCHITECTURE GEOMETRY ===")
	var campus_scn = load("res://scenes/campus.tscn")
	var campus = campus_scn.instantiate()
	root.add_child(campus)
	
	# Check StaticBodies and CollisionShapes in the scene
	var bodies = []
	find_nodes_of_type(campus, "StaticBody3D", bodies)
	print("Found %d StaticBody3D nodes" % bodies.size())
	for b in bodies:
		var glob_pos = b.global_position
		print("Body: %s at global pos %s (layer: %d, mask: %d)" % [b.name, glob_pos, b.collision_layer, b.collision_mask])
		for c in b.get_children():
			if c is CollisionShape3D:
				print("   -> CollisionShape3D %s: shape=%s, pos=%s" % [c.name, c.shape, c.position])
				if c.shape is BoxShape3D:
					print("      size: %s" % c.shape.size)

	# Check visual meshes around stairs (X ~ 5.0, Z ~ -7.5 to -1.0)
	var meshes = []
	find_nodes_of_type(campus, "MeshInstance3D", meshes)
	print("\nTotal meshes: %d" % meshes.size())
	var stair_meshes = []
	for m in meshes:
		var gpos = m.global_position
		if (gpos.x >= 3.5 and gpos.x <= 6.5 and gpos.z >= -8.0 and gpos.z <= -1.0) or ("stair" in m.name.to_lower()) or ("step" in m.name.to_lower()):
			stair_meshes.append(m)
	print("Found %d meshes near/related to stairs:" % stair_meshes.size())
	for sm in stair_meshes:
		print("  - %s at %s (parent: %s)" % [sm.name, sm.global_position, sm.get_parent().name])

	# Test player movement up stairs!
	print("\n--- SIMULATING PLAYER WALKING UP STAIRS ---")
	var player_scn = load("res://scenes/player.tscn")
	var player: CharacterBody3D = player_scn.instantiate()
	root.add_child(player)
	player.global_position = Vector3(5.0, 0.35, -7.5) # Just before stair 1
	player.velocity = Vector3(0, 0, 4.0) # moving toward -Z or +Z? Stair goes from Z=-7.3 to Z=-1.3. Moving in +Z direction (+Z = 4.0 m/s)
	print("Player start pos: %s" % player.global_position)
	
	for step in range(60): # 1 second at 60 fps
		# Direction is +Z (toward Z = -1.3, up the stairs)
		player.velocity.x = 0
		player.velocity.z = 4.0 # moving toward +Z (which is -Z in Blender, up toward second floor)
		player.velocity.y -= 18.0 * (1.0 / 60.0) # gravity
		player.move_and_slide()
		if step % 10 == 0 or step == 59:
			print("Step %d: pos=%s, on_floor=%s, floor_normal=%s" % [step, player.global_position, player.is_on_floor(), player.get_floor_normal()])

	quit(0)

func find_nodes_of_type(node: Node, type_str: String, out_arr: Array) -> void:
	if node.is_class(type_str):
		out_arr.append(node)
	for c in node.get_children():
		find_nodes_of_type(c, type_str, out_arr)
