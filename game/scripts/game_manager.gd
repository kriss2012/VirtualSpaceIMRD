extends Node

# Global signals
signal interaction_available(prompt_text: String)
signal interaction_unavailable()
signal notification_posted(message: String)
signal dialogue_started(speaker_name: String, lines: Array)
signal dialogue_ended()
signal objective_updated(objective_text: String)
signal stats_updated(level: int, xp: int, next_xp: int)

enum GameState {
	MENU,
	PLAYING,
	PAUSED,
	DIALOGUE
}

var current_state: GameState = GameState.MENU
var active_interactable = null
var is_collision_debug_enabled: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func change_state(new_state: GameState) -> void:
	current_state = new_state
	match current_state:
		GameState.PLAYING:
			get_tree().paused = false
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
		GameState.PAUSED:
			get_tree().paused = true
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
		GameState.DIALOGUE:
			get_tree().paused = false
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
		GameState.MENU:
			get_tree().paused = false
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)


func start_game() -> void:
	change_state(GameState.PLAYING)
	get_tree().change_scene_to_file("res://scenes/campus.tscn")


func return_to_main_menu() -> void:
	change_state(GameState.MENU)
	get_tree().change_scene_to_file("res://scenes/main_menu.tscn")


func toggle_pause() -> void:
	if current_state == GameState.PLAYING:
		change_state(GameState.PAUSED)
	elif current_state == GameState.PAUSED:
		change_state(GameState.PLAYING)


func post_notification(message: String) -> void:
	emit_signal("notification_posted", message)


func set_active_interactable(obj, prompt_text: String) -> void:
	active_interactable = obj
	emit_signal("interaction_available", prompt_text)


func clear_active_interactable(obj) -> void:
	if active_interactable == obj:
		active_interactable = null
		emit_signal("interaction_unavailable")


func trigger_dialogue(speaker: String, lines: Array) -> void:
	change_state(GameState.DIALOGUE)
	emit_signal("dialogue_started", speaker, lines)


func end_dialogue() -> void:
	change_state(GameState.PLAYING)
	emit_signal("dialogue_ended")
