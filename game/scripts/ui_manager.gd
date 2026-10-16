extends Control

@onready var interaction_label: Label = $HUD/InteractionPanel/InteractionLabel
@onready var interaction_panel: PanelContainer = $HUD/InteractionPanel
@onready var objective_label: Label = $HUD/ObjectivePanel/ObjectiveLabel
@onready var level_label: Label = $HUD/StatsPanel/VBox/HBox/LevelLabel
@onready var xp_bar: ProgressBar = $HUD/StatsPanel/VBox/XPProgressBar
@onready var xp_text: Label = $HUD/StatsPanel/VBox/XPTextLabel
@onready var toast_container: VBoxContainer = $HUD/ToastContainer

# Dialogue UI
@onready var dialogue_panel: PanelContainer = $DialoguePanel
@onready var speaker_label: Label = $DialoguePanel/VBox/SpeakerLabel
@onready var dialogue_label: Label = $DialoguePanel/VBox/DialogueLabel
@onready var next_button: Button = $DialoguePanel/VBox/HBox/NextButton

# Pause Menu
@onready var pause_menu: Control = $PauseMenu
@onready var resume_button: Button = $PauseMenu/Center/Panel/VBox/ResumeButton
@onready var save_button: Button = $PauseMenu/Center/Panel/VBox/SaveButton
@onready var load_button: Button = $PauseMenu/Center/Panel/VBox/LoadButton
@onready var menu_button: Button = $PauseMenu/Center/Panel/VBox/MenuButton
@onready var quit_button: Button = $PauseMenu/Center/Panel/VBox/QuitButton

var current_dialogue_lines: Array = []
var dialogue_index: int = 0


func _ready() -> void:
	# Connect to GameManager signals
	GameManager.interaction_available.connect(_on_interaction_available)
	GameManager.interaction_unavailable.connect(_on_interaction_unavailable)
	GameManager.notification_posted.connect(_on_notification_posted)
	GameManager.dialogue_started.connect(_on_dialogue_started)
	GameManager.dialogue_ended.connect(_on_dialogue_ended)
	GameManager.objective_updated.connect(_on_objective_updated)
	GameManager.stats_updated.connect(_on_stats_updated)

	# Initial UI state
	interaction_panel.visible = false
	dialogue_panel.visible = false
	pause_menu.visible = false

	# Connect Pause Menu Buttons
	if resume_button:
		resume_button.pressed.connect(_on_resume_pressed)
	if save_button:
		save_button.pressed.connect(_on_save_pressed)
	if load_button:
		load_button.pressed.connect(_on_load_pressed)
	if menu_button:
		menu_button.pressed.connect(_on_menu_pressed)
	if quit_button:
		quit_button.pressed.connect(_on_quit_pressed)
	if next_button:
		next_button.pressed.connect(_on_next_dialogue_pressed)

	# Populate initial stats and objectives
	_on_stats_updated(MissionManager.level, MissionManager.xp, MissionManager.get_next_level_xp())
	_on_objective_updated(MissionManager.get_current_objective_text())


func _process(_delta: float) -> void:
	if pause_menu:
		pause_menu.visible = (GameManager.current_state == GameManager.GameState.PAUSED)


func _on_interaction_available(text: String) -> void:
	if interaction_label and interaction_panel:
		interaction_label.text = text
		interaction_panel.visible = true


func _on_interaction_unavailable() -> void:
	if interaction_panel:
		interaction_panel.visible = false


func _on_objective_updated(text: String) -> void:
	if objective_label:
		objective_label.text = text


func _on_stats_updated(lvl: int, current_xp: int, next_xp: int) -> void:
	if level_label:
		level_label.text = "Level " + str(lvl)
	if xp_bar:
		xp_bar.max_value = next_xp
		xp_bar.value = current_xp
	if xp_text:
		xp_text.text = str(current_xp) + " / " + str(next_xp) + " XP"


func _on_notification_posted(message: String) -> void:
	if not toast_container:
		return
	var toast = Label.new()
	toast.text = message
	toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	toast.add_theme_color_override("font_color", Color(1.0, 0.92, 0.45, 1.0))
	toast_container.add_child(toast)

	var tween = create_tween()
	tween.tween_interval(3.0)
	tween.tween_property(toast, "modulate:a", 0.0, 0.8)
	tween.tween_callback(toast.queue_free)


func _on_dialogue_started(speaker: String, lines: Array) -> void:
	current_dialogue_lines = lines
	dialogue_index = 0
	if speaker_label:
		speaker_label.text = speaker
	if dialogue_panel:
		dialogue_panel.visible = true
	_show_current_dialogue_line()


func _show_current_dialogue_line() -> void:
	if dialogue_index < current_dialogue_lines.size():
		if dialogue_label:
			dialogue_label.text = current_dialogue_lines[dialogue_index]
		if next_button:
			if dialogue_index == current_dialogue_lines.size() - 1:
				next_button.text = "Close [E]"
			else:
				next_button.text = "Next [E]"
	else:
		_on_dialogue_ended()


func _on_next_dialogue_pressed() -> void:
	dialogue_index += 1
	if dialogue_index < current_dialogue_lines.size():
		_show_current_dialogue_line()
	else:
		GameManager.end_dialogue()


func _on_dialogue_ended() -> void:
	if dialogue_panel:
		dialogue_panel.visible = false


func _on_resume_pressed() -> void:
	GameManager.change_state(GameManager.GameState.PLAYING)


func _on_save_pressed() -> void:
	SaveManager.save_game()


func _on_load_pressed() -> void:
	SaveManager.load_game()


func _on_menu_pressed() -> void:
	GameManager.return_to_main_menu()


func _on_quit_pressed() -> void:
	get_tree().quit()
