extends Node

const SAVE_PATH = "user://imrd_game_save.json"


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func has_save() -> bool:
	return FileAccess.file_exists(SAVE_PATH)


func save_game() -> bool:
	var save_data = {
		"version": 1,
		"timestamp": Time.get_datetime_string_from_system(),
		"level": MissionManager.level,
		"xp": MissionManager.xp,
		"inventory": MissionManager.inventory,
		"missions": MissionManager.missions
	}

	var file = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if not file:
		print("[SaveManager] Error opening save file for writing: ", FileAccess.get_open_error())
		return false

	var json_str = JSON.stringify(save_data, "\t")
	file.store_string(json_str)
	file.close()
	print("[SaveManager] Game state successfully saved to: ", SAVE_PATH)
	GameManager.post_notification("Progress auto-saved successfully.")
	return true


func load_game() -> bool:
	if not has_save():
		print("[SaveManager] No save file found at: ", SAVE_PATH)
		return false

	var file = FileAccess.open(SAVE_PATH, FileAccess.READ)
	if not file:
		print("[SaveManager] Error opening save file for reading.")
		return false

	var content = file.get_as_text()
	file.close()

	var json = JSON.new()
	var error = json.parse(content)
	if error != OK:
		print("[SaveManager] JSON parse error: ", json.get_error_message())
		return false

	var data = json.data
	if not data is Dictionary:
		print("[SaveManager] Invalid save format (not a dictionary).")
		return false

	if data.has("level"):
		MissionManager.level = int(data["level"])
	if data.has("xp"):
		MissionManager.xp = int(data["xp"])
	if data.has("inventory") and data["inventory"] is Array:
		MissionManager.inventory.clear()
		for item in data["inventory"]:
			MissionManager.inventory.append(str(item))
	if data.has("missions") and data["missions"] is Dictionary:
		for k in data["missions"].keys():
			if MissionManager.missions.has(k):
				MissionManager.missions[k] = data["missions"][k]

	GameManager.emit_signal("stats_updated", MissionManager.level, MissionManager.xp, MissionManager.get_next_level_xp())
	GameManager.emit_signal("objective_updated", MissionManager.get_current_objective_text())
	GameManager.post_notification("Progress restored successfully.")
	print("[SaveManager] Game state successfully loaded.")
	return true
