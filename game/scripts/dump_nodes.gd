extends SceneTree

var frame: int = 0

func _init():
	change_scene_to_file("res://scenes/campus.tscn")

func _process(delta: float) -> bool:
	frame += 1
	if frame == 3:
		var root_node = root.get_node_or_null("Campus")
		if root_node:
			var port = root_node.find_child("IMRDEntrancePortico", true, false)
			if port:
				print_all(port)
		quit()
		return true
	return false

func print_all(node: Node):
	if node is MeshInstance3D and node.mesh:
		print("PORTICO: ", node.name, " path=", node.get_path(), " gp=", node.global_position, " aabb=", node.mesh.get_aabb().size)
	for c in node.get_children():
		print_all(c)
