extends SceneTree

func _init():
	var scene = load("res://scenes/campus.tscn").instantiate()
	var r_l = scene.find_child("Rail_Stair_L", true, false)
	var g_l = scene.find_child("StairVoidGuardLeft", true, false)
	print("Rail_Stair_L found: ", r_l != null)
	if r_l and r_l is MeshInstance3D:
		var aabb = r_l.get_aabb()
		print("Rail_Stair_L AABB: ", aabb)
		print("Rail_Stair_L global_pos: ", r_l.global_position)
	print("StairVoidGuardLeft found: ", g_l != null)
	if g_l:
		print("StairVoidGuardLeft pos: ", g_l.position)
		var h = g_l.find_child("Handrail", true, false)
		if h and h.mesh:
			print("StairVoidGuardLeft Handrail size: ", h.mesh.size)
		var p4 = g_l.find_child("Post4", true, false)
		print("Post4 found: ", p4 != null)
	quit()
