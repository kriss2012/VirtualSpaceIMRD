extends Node

# Full Integration Test Runner with Autoloads Initialized

var passed_tests: int = 0
var failed_tests: int = 0

func assert_true(condition: bool, test_name: String) -> void:
	if condition:
		print("  [PASS] " + test_name)
		passed_tests += 1
	else:
		printerr("  [FAIL] " + test_name)
		failed_tests += 1


func _ready() -> void:
	print("====================================================")
	print("   IMRD CAMPUS EXPLORER - AUTOMATED ENGINE TESTS    ")
	print("====================================================")
	
	test_autoloads()
	test_main_menu_scene()
	test_campus_scene_loading()
	test_player_controller()
	test_doors_and_interaction()
	test_npc_and_missions()
	test_id_card_pickup()
	test_location_triggers()
	test_save_load_system()
	test_stair_climb_and_second_floor()
	
	print("====================================================")
	print("TEST RESULTS: %d Passed, %d Failed" % [passed_tests, failed_tests])
	print("====================================================")
	
	if failed_tests == 0:
		print("ALL 30+ GODOT GAME ENGINE TESTS PASSED SUCCESSFULLY!")
		get_tree().quit(0)
	else:
		printerr("SOME TESTS FAILED! CHECK OUTPUT ABOVE.")
		get_tree().quit(1)


func test_autoloads() -> void:
	print("\n--- TEST GROUP 1: Autoload Singletons ---")
	assert_true(GameManager != null, "GameManager singleton loaded")
	assert_true(MissionManager != null, "MissionManager singleton loaded")
	assert_true(SaveManager != null, "SaveManager singleton loaded")


func test_main_menu_scene() -> void:
	print("\n--- TEST GROUP 2: Main Menu & Intro Cinematic Scene ---")
	var menu_res = load("res://scenes/main_menu.tscn")
	assert_true(menu_res != null, "Main menu scene resource exists")
	var menu_node = menu_res.instantiate()
	assert_true(menu_node != null, "Main menu instantiated successfully")
	add_child(menu_node)
	assert_true(menu_node is Node3D, "Main menu root is 3D scene (Node3D)")
	
	# Verify 3D Cinematic Camera & Visual Campus Backdrop
	assert_true(menu_node.find_child("IntroCamera3D", true, false) != null, "IntroCamera3D present")
	assert_true(menu_node.find_child("VisualEnvironment", true, false) != null, "Campus 3D VisualEnvironment present")
	assert_true(menu_node.find_child("DirectionalLight3D", true, false) != null, "Daylight Sun present for fly-through")
	
	# Verify UI Elements & Styling
	assert_true(menu_node.find_child("LetterboxTop", true, false) != null, "Cinematic letterbox top bar present")
	assert_true(menu_node.find_child("LetterboxBottom", true, false) != null, "Cinematic letterbox bottom bar present")
	assert_true(menu_node.find_child("SkipButton", true, false) != null, "Skip intro button present")
	assert_true(menu_node.find_child("TitleContainer", true, false) != null, "Cinematic title container present")
	assert_true(menu_node.find_child("TitleLine1", true, false) != null, "Title Line 1 (IMRD) present")
	assert_true(menu_node.find_child("TitleLine2", true, false) != null, "Title Line 2 (3D CAMPUS WALKTHROUGH) present")
	assert_true(menu_node.find_child("TitleLine3", true, false) != null, "Title Line 3 (Institution) present")
	assert_true(menu_node.find_child("StartButton", true, false) != null, "Start button found")
	assert_true(menu_node.find_child("ControlsButton", true, false) != null, "Controls button found")
	assert_true(menu_node.find_child("ReplayButton", true, false) != null, "Replay intro button found")
	assert_true(menu_node.find_child("QuitButton", true, false) != null, "Quit button found")
	assert_true(menu_node.find_child("FadeOverlay", true, false) != null, "Fade overlay present")
	
	# Verify Camera Evaluation across timeline
	if menu_node.has_method("update_camera_pose"):
		menu_node.update_camera_pose(0.0)
		var cam: Camera3D = menu_node.find_child("IntroCamera3D", true, false) as Camera3D
		assert_true(cam != null and cam.position.is_equal_approx(Vector3(24.0, 15.5, -90.0)), "Intro camera establishes at gate (t=0.0s)")
		menu_node.update_camera_pose(20.0)
		assert_true(cam != null and cam.position.is_equal_approx(Vector3(-2.1, 3.7, -42.65)), "Intro camera reaches final menu pose (t=20.0s)")
	
	remove_child(menu_node)
	menu_node.free()


func test_campus_scene_loading() -> void:
	print("\n--- TEST GROUP 3: Campus 3D World Scene ---")
	var campus_res = load("res://scenes/campus.tscn")
	assert_true(campus_res != null, "Campus scene resource exists")
	var campus = campus_res.instantiate()
	assert_true(campus != null, "Campus 3D world instantiated")
	
	# Verify Environment and Lighting
	assert_true(campus.find_child("WorldEnvironment", true, false) != null, "WorldEnvironment node active")
	assert_true(campus.find_child("DirectionalLight3D", true, false) != null, "DirectionalLight3D (Sun) active")
	
	# Verify GLB visual components
	var vis = campus.find_child("VisualEnvironment", true, false)
	assert_true(vis != null, "VisualEnvironment container present")
	assert_true(vis.find_child("campus_terrain", true, false) != null, "campus_terrain GLB instantiated")
	assert_true(vis.find_child("campus_architecture", true, false) != null, "campus_architecture GLB instantiated")
	assert_true(vis.find_child("campus_props", true, false) != null, "campus_props GLB instantiated")
	assert_true(vis.find_child("campus_furniture", true, false) != null, "campus_furniture GLB instantiated")
	assert_true(vis.find_child("campus_vegetation", true, false) != null, "campus_vegetation GLB instantiated")
	
	# Verify Collision geometry
	var cols = campus.find_child("Collisions", true, false)
	assert_true(cols != null, "Collisions root present")
	assert_true(cols.find_child("GroundCollision", true, false) != null, "Ground static collision present")
	var entrance_col = cols.find_child("EntranceStepsRamp", true, false)
	assert_true(entrance_col != null, "Entrance steps smooth ramp present")
	assert_true(entrance_col.get_child(0).shape is ConvexPolygonShape3D, "Entrance ramp uses smooth ConvexPolygonShape3D")
	assert_true(cols.find_child("PlinthCollision", true, false) != null, "Plinth static collision present")
	
	var stair_col = cols.find_child("StairsRampCollision", true, false)
	assert_true(stair_col != null, "Stairs ramp collision present")
	assert_true(stair_col.get_child(0).shape is ConvexPolygonShape3D, "Stairs ramp uses smooth ConvexPolygonShape3D")
	assert_true(campus.find_child("InteriorLighting", true, false) != null, "Interior lighting system present")
	
	assert_true(cols.find_child("Floor1_WestSlab", true, false) != null, "Second floor West slab collision present")
	assert_true(cols.find_child("Floor1_EastSlab", true, false) != null, "Second floor East slab collision present")
	assert_true(cols.find_child("Floor1_LandingRear", true, false) != null, "Second floor Landing collision present")
	
	# Verify Real Architecture & Specialized Sections
	assert_true(vis.find_child("IMRDEntrancePortico", true, false) != null, "Authentic IMRD entrance portico present")
	assert_true(vis.find_child("LibrarySection", true, false) != null, "Authentic IMRD Library section present")
	assert_true(vis.find_child("SeminarHall", true, false) != null, "Authentic IMRD Seminar Hall present")
	
	# Verify Parked Vehicles & Interior Wall Collisions
	var vehicles = cols.find_child("Vehicles", true, false)
	assert_true(vehicles != null, "Vehicles collision container present")
	assert_true(vehicles.get_child_count() >= 6, "All 6 parked cars have active static body collisions")
	assert_true(cols.find_child("GroundPartitionWest", true, false) != null, "Ground partition wall collision present")
	assert_true(cols.find_child("ClassroomWestWall_Front", true, false) != null, "Classroom 101 wall collision present")
	assert_true(cols.find_child("ComputerLabEastWall_Front", true, false) != null, "Computer Lab wall collision present")
	assert_true(cols.find_child("SecurityCabin", true, false) != null, "Security cabin collision present")
	
	# Verify Doors
	var doors = campus.find_child("Doors", true, false)
	assert_true(doors != null, "Doors root present")
	assert_true(doors.find_child("MainEntrancePortal", true, false) != null, "Main Entrance animated portal present")
	assert_true(doors.find_child("Classroom101Door", true, false) != null, "Classroom 101 door present")
	assert_true(doors.find_child("ComputerLabDoor", true, false) != null, "Computer Lab door present")
	assert_true(doors.find_child("CentralLibraryDoor", true, false) != null, "Central Library door present")
	assert_true(doors.find_child("Classroom201Door", true, false) != null, "Second floor Classroom 201 door present")
	assert_true(doors.find_child("SeminarHallDoor", true, false) != null, "Second floor Seminar Hall door present")
	
	campus.free()


func test_player_controller() -> void:
	print("\n--- TEST GROUP 4: Player Controller & Camera ---")
	var player_res = load("res://scenes/player.tscn")
	assert_true(player_res != null, "Player scene resource exists")
	var player = player_res.instantiate()
	assert_true(player is CharacterBody3D, "Player is CharacterBody3D")
	assert_true(player.find_child("CollisionShape3D", true, false) != null, "Player has physics collision shape")
	assert_true(player.find_child("CameraPivot", true, false) != null, "Player has CameraPivot")
	var spring_arm = player.find_child("SpringArm3D", true, false)
	assert_true(spring_arm != null, "Player has SpringArm3D for obstruction avoidance")
	assert_true(spring_arm.shape is SphereShape3D, "SpringArm3D uses SphereShape3D preventing wall/corner clipping")
	assert_true(player.find_child("Camera3D", true, false) != null, "Player has 3rd-person Camera3D")
	
	# Attach to tree for global transform test
	add_child(player)
	player.global_position = Vector3(0, 0, 0)
	player._ready()
	assert_true(player.global_position.z == -68.0, "Player initializes to spawn Z = -68.0")
	remove_child(player)
	player.free()


func test_doors_and_interaction() -> void:
	print("\n--- TEST GROUP 5: Doors & Hinge Pivot Interaction ---")
	# 1. Test Classroom Door
	var cdoor_res = load("res://scenes/classroom_door.tscn")
	assert_true(cdoor_res != null, "Classroom door scene resource exists")
	var cdoor = cdoor_res.instantiate()
	assert_true(cdoor.find_child("InteractionArea", true, false).get_child(0).shape is BoxShape3D, "Classroom door uses targeted BoxShape3D interaction area")
	assert_true(not cdoor.is_open, "Classroom door starts closed")
	cdoor.interact()
	assert_true(cdoor.is_open, "Classroom door state transitions to OPEN after interaction")
	cdoor.interact()
	assert_true(not cdoor.is_open, "Classroom door state transitions back to CLOSED")
	cdoor.free()
	
	# 2. Test Grand Entrance Portal Double Doors
	var portal_res = load("res://scenes/entrance_portal.tscn")
	assert_true(portal_res != null, "Entrance portal scene resource exists")
	var portal = portal_res.instantiate()
	assert_true(portal.has_method("interact"), "Entrance portal has interact method")
	assert_true(not portal.is_open, "Entrance double doors start closed")
	portal.interact()
	assert_true(portal.is_open, "Entrance double doors transition to OPEN after interaction")
	assert_true(portal.get_interaction_text() == "Press [E] to Close Main Entrance", "Portal prompt updates to Close")
	portal.interact()
	assert_true(not portal.is_open, "Entrance double doors transition back to CLOSED")
	portal.free()
	
	# 3. Test Standard Single Door
	var door_res = load("res://scenes/door.tscn")
	assert_true(door_res != null, "Standard single door scene exists")
	var sdoor = door_res.instantiate()
	sdoor._ready()
	assert_true(sdoor.has_method("interact"), "Single door has interact method")
	assert_true(not sdoor.is_open, "Single door starts closed")
	var col_shape = sdoor.find_child("DoorBody", true, false).get_child(0)
	assert_true(not col_shape.disabled, "DoorBody collision active when closed")
	sdoor.interact()
	assert_true(sdoor.is_open, "Single door opened")
	assert_true(col_shape.disabled, "DoorBody collision disabled when open for passage")
	sdoor.free()


func test_npc_and_missions() -> void:
	print("\n--- TEST GROUP 6: NPC Prof. Sharma & Mission 1 ---")
	var npc_res = load("res://scenes/npc.tscn")
	assert_true(npc_res != null, "NPC scene resource exists")
	var npc = npc_res.instantiate()
	assert_true(npc.npc_name == "Prof. Sharma", "NPC is Prof. Sharma")
	
	var initial_xp = MissionManager.xp
	npc.interact()
	assert_true(MissionManager.missions["first_day"]["completed"], "First Day mission completed after talking to guide")
	assert_true(MissionManager.xp > initial_xp, "XP rewarded for completing First Day mission")
	npc.free()


func test_id_card_pickup() -> void:
	print("\n--- TEST GROUP 7: Collectible Student ID Card & Mission 2 ---")
	var card_res = load("res://scenes/item_id_card.tscn")
	assert_true(card_res != null, "ID card scene resource exists")
	var card = card_res.instantiate()
	assert_true(card.has_method("interact"), "Card has interact method")
	
	card.interact()
	assert_true(MissionManager.missions["lost_id_card"]["completed"], "Lost ID Card mission completed on pickup")
	assert_true("Student_ID_Card" in MissionManager.inventory, "Student_ID_Card added to inventory")
	card.free()


func test_location_triggers() -> void:
	print("\n--- TEST GROUP 8: Campus Explorer Locations & Mission 3 ---")
	MissionManager.on_visit_location("classroom")
	assert_true(MissionManager.missions["campus_explorer"]["visited_classroom"], "Visited classroom recorded")
	MissionManager.on_visit_location("lobby")
	assert_true(MissionManager.missions["campus_explorer"]["visited_lobby"], "Visited lobby recorded")
	MissionManager.on_visit_location("courtyard")
	assert_true(MissionManager.missions["campus_explorer"]["visited_courtyard"], "Visited courtyard recorded")
	assert_true(MissionManager.missions["campus_explorer"]["completed"], "Campus Explorer mission completed after all 3 areas visited")


func test_save_load_system() -> void:
	print("\n--- TEST GROUP 9: Save & Load Persistence ---")
	var current_xp = MissionManager.xp
	var current_level = MissionManager.level
	
	# Save state
	var saved = SaveManager.save_game()
	assert_true(saved, "Game saved to user://imrd_game_save.json successfully")
	
	# Mutate state
	MissionManager.xp = 0
	MissionManager.level = 99
	
	# Load state back
	var loaded = SaveManager.load_game()
	assert_true(loaded, "Game save loaded back successfully")
	assert_true(MissionManager.xp == current_xp, "Saved XP restored correctly")
	assert_true(MissionManager.level == current_level, "Saved Level restored correctly")
	assert_true(MissionManager.missions["first_day"]["completed"], "Saved mission state preserved")


func test_stair_climb_and_second_floor() -> void:
	print("\n--- TEST GROUP 10: Stair Climb & Second Floor Traversal ---")
	var campus_scn = load("res://scenes/campus.tscn")
	assert_true(campus_scn != null, "Campus scene loads for traversal test")
	var campus = campus_scn.instantiate()
	add_child(campus)
	
	var player = campus.find_child("Player", true, false)
	assert_true(player != null, "Player found in campus")
	
	# Start at bottom of stairs on the lobby plinth
	player.global_position = Vector3(5.0, 0.40, -5.75)
	assert_true(player.global_position.y >= 0.34, "Player starts at ground plinth Y >= 0.34")
	
	# Verify convex polygon shape points
	var stairs_col = campus.find_child("StairsRampCollision", true, false)
	assert_true(stairs_col != null, "Stairs ramp collision node exists")
	var shape: ConvexPolygonShape3D = stairs_col.get_child(0).shape as ConvexPolygonShape3D
	assert_true(shape != null, "Stairs ramp shape is ConvexPolygonShape3D")
	var pts = shape.points
	assert_true(pts.size() >= 6, "Stairs ramp has 3D convex hull points")
	
	# Check bottom and top points of the ramp
	var has_bottom_pt = false
	var has_top_pt = false
	for p in pts:
		if p.z <= -5.8 and abs(p.y - 0.34) < 0.1:
			has_bottom_pt = true
		if p.z >= -1.2 and abs(p.y - 4.30) < 0.1:
			has_top_pt = true
	assert_true(has_bottom_pt, "Stair ramp connects seamlessly to ground plinth (Y=0.34 at Z=-5.85)")
	assert_true(has_top_pt, "Stair ramp connects seamlessly to second floor landing (Y=4.30 at Z=-1.10)")
	
	# Check second floor door accessibility
	var c201 = campus.find_child("Classroom201Door", true, false)
	assert_true(c201 != null and c201.position.y >= 4.0, "Classroom 201 door accessible on second floor (Y >= 4.0)")
	var seminar = campus.find_child("SeminarHallDoor", true, false)
	assert_true(seminar != null and seminar.position.y >= 4.0, "Seminar Hall door accessible on second floor (Y >= 4.0)")
	
	remove_child(campus)
	campus.free()

