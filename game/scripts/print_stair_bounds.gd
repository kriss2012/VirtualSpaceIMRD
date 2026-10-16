@tool
extends SceneTree

func _init() -> void:
	var arch_scn = load("res://assets/models/campus_architecture.glb")
	var arch = arch_scn.instantiate()
	var min_p = Vector3(1e9, 1e9, 1e9)
	var max_p = Vector3(-1e9, -1e9, -1e9)
	for i in range(1, 22):
		var step_name = "Stair_Step_%02d" % i
		var step = arch.find_child(step_name, true, false)
		if step:
			var aabb = step.mesh.get_aabb()
			var gpos = step.global_position
			var p0 = gpos + aabb.position
			var p1 = gpos + aabb.position + aabb.size
			min_p.x = min(min_p.x, p0.x)
			min_p.y = min(min_p.y, p0.y)
			min_p.z = min(min_p.z, p0.z)
			max_p.x = max(max_p.x, p1.x)
			max_p.y = max(max_p.y, p1.y)
			max_p.z = max(max_p.z, p1.z)
			if i == 1 or i == 21:
				print("Step %s: global_pos=%s, aabb=%s, world=[%s to %s]" % [step_name, gpos, aabb, p0, p1])
	print("OVERALL STAIR BOUNDING BOX: min=%s, max=%s" % [min_p, max_p])
	quit(0)
