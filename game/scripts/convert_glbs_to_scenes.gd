@tool
extends SceneTree

func _init() -> void:
	print("=== Converting GLBs to Native Godot TSCN Scenes ===")
	var dir = DirAccess.open("res://")
	if not dir.dir_exists("res://scenes/models"):
		dir.make_dir_recursive("res://scenes/models")
		
	var models = [
		"campus_architecture",
		"campus_terrain",
		"campus_props",
		"campus_furniture",
		"campus_vegetation",
		"campus_doors",
		"character_student",
		"npc_guide"
	]
	for m in models:
		var glb_path = "res://assets/models/" + m + ".glb"
		var tscn_path = "res://scenes/models/" + m + ".tscn"
		var gltf = GLTFDocument.new()
		var state = GLTFState.new()
		var err = gltf.append_from_file(glb_path, state)
		if err != OK:
			print("ERROR loading ", glb_path, " code: ", err)
			continue
		var node = gltf.generate_scene(state)
		node.name = m
		var packed = PackedScene.new()
		var pack_err = packed.pack(node)
		if pack_err != OK:
			print("ERROR packing ", m, " code: ", pack_err)
			continue
		var save_err = ResourceSaver.save(packed, tscn_path)
		print("SUCCESS: ", m, " -> ", tscn_path, " (save_err: ", save_err, ")")
	print("=== Conversion Complete ===")
	quit()
