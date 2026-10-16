extends SceneTree

# Automated Engine & Gameplay Validation Test Suite
# Runs headless under Godot CLI

var passed_tests: int = 0
var failed_tests: int = 0

func assert_true(condition: bool, test_name: String) -> void:
	if condition:
		print("  [PASS] " + test_name)
		passed_tests += 1
	else:
		printerr("  [FAIL] " + test_name)
		failed_tests += 1


func _init() -> void:
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
	
	print("====================================================")
	print("TEST RESULTS: %d Passed, %d Failed" % [passed_tests, failed_tests])
	print("====================================================")
	
	if failed_tests == 0:
		print("ALL GODOT GAME ENGINE TESTS PASSED SUCCESSFULLY!")
		quit(0)
	else:
		printerr("SOME TESTS FAILED! CHECK OUTPUT ABOVE.")
		quit(1)


func test_autoloads() -> void:
	print("\n--- TEST GROUP 1: Autoload Singletons ---")
	assert_true(GameManager != null, "GameManager singleton loaded")
	assert_true(MissionManager != null, "MissionManager singleton loaded")
	assert_true(SaveManager != null, "SaveManager singleton loaded")


func test_main_menu_scene() -> void:
	print("\n--- TEST GROUP 2: Main Menu Scene ---")
	var menu_res = load("res://scenes/main_menu.tscn")
	assert_true(menu_res != null, "Main menu scene resource exists")
	var menu_node = menu_res.instantiate()
	assert_true(menu_node != null, "Main menu instantiated successfully")
	assert_true(menu_node.find_child("BtnStart", true, false) != null, "Start button found")
	assert_true(menu_node.find_child("BtnControls", true, false) != null, "Controls button found")
	assert_true(menu_node.find_child("BtnQuit", true, false) != null, "Quit button found")
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
	assert_true(cols.find_child("PlinthCollision", true, false) != null, "Plinth static collision present")
	assert_true(cols.find_child("StairsRampCollision", true, false) != null, "Stairs ramp collision present")
	
	campus.free()


func test_player_controller() -> void:
	print("\n--- TEST GROUP 4: Player Controller & Camera ---")
	var player_res = load("res://scenes/player.tscn")
	assert_true(player_res != null, "Player scene resource exists")
	var player = player_res.instantiate()
	assert_true(player is CharacterBody3D, "Player is CharacterBody3D")
	assert_true(player.find_child("CollisionShape3D", true, false) != null, "Player has physics collision shape")
	assert_true(player.find_child("CameraPivot", true, false) != null, "Player has CameraPivot")
	assert_true(player.find_child("SpringArm3D", true, false) != null, "Player has SpringArm3D for obstruction avoidance")
	assert_true(player.find_child("Camera3D", true, false) != null, "Player has 3rd-person Camera3D")
	
	# Test spawn coordinate logic
	player.global_position = Vector3(0, 0, 0)
	player._ready()
	assert_true(player.global_position.z == -68.0, "Player initializes to spawn Z = -68.0")
	player.free()


func test_doors_and_interaction() -> void:
	print("\n--- TEST GROUP 5: Doors & Hinge Pivot Interaction ---")
	var door_res = load("res://scenes/door.tscn")
	assert_true(door_res != null, "Door scene resource exists")
	var door = door_res.instantiate()
	assert_true(door.has_method("interact"), "Door has interact method")
	assert_true(not door.is_open, "Door starts closed")
	
	# Toggle open
	door.interact()
	assert_true(door.is_open, "Door state transitions to OPEN after interaction")
	assert_true(door.get_interaction_text() == "Press [E] to Close Door", "Interaction prompt updates to Close")
	
	# Toggle close
	door.interact()
	assert_true(not door.is_open, "Door state transitions back to CLOSED after second interaction")
	door.free()


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
