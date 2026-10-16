extends Control

@onready var start_button: Button = $CenterContainer/PanelContainer/VBox/StartButton
@onready var controls_button: Button = $CenterContainer/PanelContainer/VBox/ControlsButton
@onready var quit_button: Button = $CenterContainer/PanelContainer/VBox/QuitButton
@onready var controls_dialog: AcceptDialog = $ControlsDialog


func _ready() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	start_button.pressed.connect(_on_start_pressed)
	controls_button.pressed.connect(_on_controls_pressed)
	quit_button.pressed.connect(_on_quit_pressed)


func _on_start_pressed() -> void:
	GameManager.start_game()


func _on_controls_pressed() -> void:
	if controls_dialog:
		controls_dialog.popup_centered()


func _on_quit_pressed() -> void:
	get_tree().quit()
