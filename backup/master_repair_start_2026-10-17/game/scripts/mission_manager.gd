extends Node

var level: int = 1
var xp: int = 0
var inventory: Array[String] = []

var missions: Dictionary = {
	"first_day": {
		"id": "first_day",
		"title": "First Day at IMRD",
		"description": "Meet Prof. Sharma at the entrance plaza for your campus orientation.",
		"completed": false,
		"xp": 150
	},
	"lost_id_card": {
		"id": "lost_id_card",
		"title": "Lost ID Card",
		"description": "Find the student ID card dropped near the entrance plaza walkway.",
		"has_card": false,
		"completed": false,
		"xp": 200
	},
	"campus_explorer": {
		"id": "campus_explorer",
		"title": "Campus Explorer",
		"description": "Explore the Ground Floor Classroom West, the Grand Lobby & Staircase, and the Garden Courtyard.",
		"visited_classroom": false,
		"visited_lobby": false,
		"visited_courtyard": false,
		"completed": false,
		"xp": 300
	}
}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func get_next_level_xp() -> int:
	return level * 200


func add_xp(amount: int) -> void:
	xp += amount
	var required_xp = get_next_level_xp()
	while xp >= required_xp:
		xp -= required_xp
		level += 1
		required_xp = get_next_level_xp()
		GameManager.post_notification("LEVEL UP! You are now Level " + str(level) + "!")
	GameManager.emit_signal("stats_updated", level, xp, required_xp)


func get_current_objective_text() -> String:
	if not missions["first_day"]["completed"]:
		return "Orientation: Meet Prof. Sharma at the entrance plaza [Press E]"
	elif not missions["lost_id_card"]["completed"]:
		return "Mission: Find the lost Student ID card along the plaza walkway"
	elif not missions["campus_explorer"]["completed"]:
		var places: Array[String] = []
		if not missions["campus_explorer"]["visited_classroom"]:
			places.append("Classroom West")
		if not missions["campus_explorer"]["visited_lobby"]:
			places.append("Grand Lobby")
		if not missions["campus_explorer"]["visited_courtyard"]:
			places.append("Garden Courtyard")
		return "Explore: Visit " + ", ".join(places)
	else:
		return "Campus Orientation Complete! Enjoy exploring RCPET's IMRD."


func on_talk_to_guide() -> Array[String]:
	var notifs: Array[String] = []
	if not missions["first_day"]["completed"]:
		missions["first_day"]["completed"] = true
		add_xp(missions["first_day"]["xp"])
		notifs.append("[XP +150] Completed: First Day at IMRD")
		notifs.append("New Objective: Find the Lost Student ID Card near the plaza walkway!")
		GameManager.emit_signal("objective_updated", get_current_objective_text())
		SaveManager.save_game()
	return notifs


func on_pickup_id_card() -> Array[String]:
	var notifs: Array[String] = []
	if not missions["lost_id_card"]["has_card"]:
		missions["lost_id_card"]["has_card"] = true
		missions["lost_id_card"]["completed"] = true
		inventory.append("Student_ID_Card")
		add_xp(missions["lost_id_card"]["xp"])
		notifs.append("[Item Acquired] Student ID Card added to inventory")
		notifs.append("[XP +200] Completed: Lost ID Card!")
		notifs.append("Next Mission: Explore the campus classroom, lobby, and courtyard!")
		GameManager.emit_signal("objective_updated", get_current_objective_text())
		SaveManager.save_game()
	return notifs


func on_visit_location(loc_name: String) -> void:
	var m = missions["campus_explorer"]
	if m["completed"]:
		return

	var updated: bool = false
	if loc_name == "classroom" and not m["visited_classroom"]:
		m["visited_classroom"] = true
		updated = true
		GameManager.post_notification("[Explored] Ground Floor Classroom West")
	elif loc_name == "lobby" and not m["visited_lobby"]:
		m["visited_lobby"] = true
		updated = true
		GameManager.post_notification("[Explored] Grand Central Lobby & Staircase")
	elif loc_name == "courtyard" and not m["visited_courtyard"]:
		m["visited_courtyard"] = true
		updated = true
		GameManager.post_notification("[Explored] Garden Courtyard & Plaza")

	if updated:
		if m["visited_classroom"] and m["visited_lobby"] and m["visited_courtyard"]:
			m["completed"] = true
			add_xp(m["xp"])
			GameManager.post_notification("[XP +300] All Campus Explorer locations discovered!")
			SaveManager.save_game()
		GameManager.emit_signal("objective_updated", get_current_objective_text())
