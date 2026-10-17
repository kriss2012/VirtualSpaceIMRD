extends SceneTree

func _init():
	var root = Window.new()
	root.size = Vector2i(1280, 720)
	var scene = load("res://scenes/campus.tscn").instantiate()
	root.add_child(scene)
	
	var cam = Camera3D.new()
	cam.position = Vector3(3.2, 5.0, -0.6)
	cam.look_at(Vector3(5.0, 4.0, -3.0), Vector3.UP)
	cam.current = true
	root.add_child(cam)
	
	# Let's inspect Rail_Stair_L and StairVoidGuardLeft
	var r_l = scene.find_child("Rail_Stair_L", true, false)
	var g_l = scene.find_child("StairVoidGuardLeft", true, false)
	print("r_l: ", r_l)
	print("g_l: ", g_l)
	quit()
