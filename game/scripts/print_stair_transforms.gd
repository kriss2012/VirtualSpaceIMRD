@tool
extends SceneTree

func _init() -> void:
	var arch_scn = load("res://assets/models/campus_architecture.glb")
	var arch = arch_scn.instantiate()
	root.add_child(arch)
	for name in ["Stair_Step_01", "Stair_Step_21", "Rail_Stair_L", "Rail_Stair_R", "Slab_Floor_1_Landing"]:
		var node = arch.find_child(name, true, false)
		if node:
			print("Node %s: pos=%s, rot=%s, parent=%s" % [name, node.global_position, node.rotation, node.get_parent().name])
	quit(0)
