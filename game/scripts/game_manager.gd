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

const SETTINGS_PATH: String = "user://imrd_settings.json"

var settings: Dictionary = {
	"fullscreen": false,
	"resolution_index": 0,
	"vsync": true,
	"ssao": true,
	"shadows": true,
	"glow": true,
	"master_volume": 1.0,
	"music_volume": 0.8,
	"sfx_volume": 0.9,
	"ui_sound": true,
	"mouse_sensitivity": 1.0,
	"invert_y": false,
	"fov": 70.0
}

var ui_audio_player: AudioStreamPlayer = null
var snd_hover: AudioStreamWAV = null
var snd_click: AudioStreamWAV = null
var snd_back: AudioStreamWAV = null
var snd_toggle: AudioStreamWAV = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_init_procedural_audio()
	load_settings()
	apply_settings()


func _init_procedural_audio() -> void:
	ui_audio_player = AudioStreamPlayer.new()
	ui_audio_player.bus = "Master"
	add_child(ui_audio_player)
	snd_hover = _create_beep(1200.0, 0.025, 0.15)
	snd_click = _create_beep(720.0, 0.07, 0.35)
	snd_back = _create_beep(380.0, 0.06, 0.25)
	snd_toggle = _create_beep(960.0, 0.04, 0.25)


func _create_beep(freq: float, duration: float, vol: float) -> AudioStreamWAV:
	var sample_rate: int = 22050
	var total_samples: int = int(sample_rate * duration)
	var data: PackedByteArray = PackedByteArray()
	data.resize(total_samples)
	for i in range(total_samples):
		var t = float(i) / float(sample_rate)
		var env = 1.0 - (float(i) / float(total_samples))
		var wave = sin(2.0 * PI * freq * t) * env * vol
		var byte_val = int(clampf((wave + 1.0) * 127.5, 0.0, 255.0))
		data[i] = byte_val
	var wav = AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_8_BITS
	wav.mix_rate = sample_rate
	wav.data = data
	return wav


func play_ui_sound(type: String) -> void:
	if not settings.get("ui_sound", true):
		return
	if not ui_audio_player:
		return
	match type:
		"hover":
			ui_audio_player.stream = snd_hover
		"click":
			ui_audio_player.stream = snd_click
		"back":
			ui_audio_player.stream = snd_back
		"toggle":
			ui_audio_player.stream = snd_toggle
		_:
			ui_audio_player.stream = snd_click
	ui_audio_player.play()


func load_settings() -> void:
	if not FileAccess.file_exists(SETTINGS_PATH):
		return
	var file = FileAccess.open(SETTINGS_PATH, FileAccess.READ)
	if not file:
		return
	var text = file.get_as_text()
	file.close()
	var json = JSON.new()
	if json.parse(text) == OK and json.data is Dictionary:
		for k in json.data.keys():
			settings[k] = json.data[k]


func save_settings() -> void:
	var file = FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if not file:
		return
	file.store_string(JSON.stringify(settings, "\t"))
	file.close()


func apply_settings() -> void:
	# 1. Fullscreen / Window Mode
	var is_fs: bool = settings.get("fullscreen", false)
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if is_fs else DisplayServer.WINDOW_MODE_WINDOWED)
	
	# 2. Resolution (if windowed)
	if not is_fs:
		var res_idx: int = settings.get("resolution_index", 0)
		var res: Vector2i = Vector2i(1280, 720)
		if res_idx == 1:
			res = Vector2i(1600, 900)
		elif res_idx == 2:
			res = Vector2i(1920, 1080)
		DisplayServer.window_set_size(res)
		
	# 3. Audio Volume
	var master_vol: float = settings.get("master_volume", 1.0)
	var db: float = linear_to_db(clampf(master_vol, 0.001, 1.0))
	AudioServer.set_bus_volume_db(0, db)
	AudioServer.set_bus_mute(0, master_vol <= 0.01)
	
	# 4. VSync
	var vsync_on: bool = settings.get("vsync", true)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if vsync_on else DisplayServer.VSYNC_DISABLED)


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
