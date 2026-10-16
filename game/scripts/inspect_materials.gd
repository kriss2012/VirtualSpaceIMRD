@tool
extends SceneTree

func _init() -> void:
	var arch_scn = load("res://assets/models/campus_architecture.glb")
	var arch = arch_scn.instantiate()
	var meshes = []
	find_meshes(arch, meshes)
	print("Found %d meshes in campus_architecture.glb" % meshes.size())
	for m in meshes:
		var s_mats = []
		for s in range(m.mesh.get_surface_count()):
			var sm = m.mesh.surface_get_material(s)
			s_mats.append(sm.resource_name if sm else "null")
		if "roof" in m.name.to_lower() or "stair" in m.name.to_lower() or "ceiling" in m.name.to_lower() or "slab" in m.name.to_lower() or "rail" in m.name.to_lower():
			print("Mesh: %s -> Mats: %s, Override: %s" % [m.name, s_mats, m.get_surface_override_material(0)])
	quit(0)

func find_meshes(node: Node, arr: Array) -> void:
	if node is MeshInstance3D and node.mesh:
		arr.append(node)
	for c in node.get_children():
		find_meshes(c, arr)
