extends Node3D

# ==============================================================================
# IMRD 3D Campus Explorer — Cinematic Opening Sequence & Main Menu
# Ported directly from 06_intro_cinematic.py
# ==============================================================================

# Timeline milestones (seconds)
const T_FADE_IN: float = 2.0
const T_TITLE_START: float = 10.0
const T_MENU: float = 17.0
const T_END: float = 20.0

# Exact camera keyframes from 06_intro_cinematic.py (converted to Godot coordinates)
# Blender (X, Y, Z) -> Godot (X, Z, -Y)
const INTRO_KEYS: Array = [
	{
		"name": "Establish",
		"t": 0.0,
		"pos": Vector3(24.0, 15.5, -90.0),
		"look": Vector3(0.0, 3.5, -40.0),
		"ease": true
	},
	{
		"name": "Reveal",
		"t": 2.0,
		"pos": Vector3(20.7, 14.4, -84.9),
		"look": Vector3(0.0, 3.4, -38.0),
		"ease": false
	},
	{
		"name": "OverGate",
		"t": 6.0,
		"pos": Vector3(2.0, 8.0, -56.0),
		"look": Vector3(0.0, 3.2, -22.05),
		"ease": false
	},
	{
		"name": "Entrance",
		"t": 10.0,
		"pos": Vector3(-2.5, 2.0, -21.05),
		"look": Vector3(0.0, 3.6, -9.05),
		"ease": true
	},
	{
		"name": "PullBack",
		"t": 14.0,
		"pos": Vector3(-1.8, 3.4, -38.05),
		"look": Vector3(-4.5, 6.4, -9.55),
		"ease": false
	},
	{
		"name": "Hold",
		"t": 17.0,
		"pos": Vector3(-2.0, 3.6, -41.75),
		"look": Vector3(-4.5, 6.4, -9.55),
		"ease": false
	},
	{
		"name": "End",
		"t": 20.0,
		"pos": Vector3(-2.1, 3.7, -42.65),
		"look": Vector3(-4.5, 6.4, -9.55),
		"ease": true
	}
]

var current_time: float = 0.0
var is_skipping: bool = false
var is_menu_active: bool = false

# Node references
@onready var intro_camera: Camera3D = find_child("IntroCamera3D", true, false) as Camera3D
@onready var fade_overlay: ColorRect = find_child("FadeOverlay", true, false) as ColorRect
@onready var letterbox_top: ColorRect = find_child("LetterboxTop", true, false) as ColorRect
@onready var letterbox_bottom: ColorRect = find_child("LetterboxBottom", true, false) as ColorRect
@onready var skip_button: Button = find_child("SkipButton", true, false) as Button
@onready var title_container: Control = find_child("TitleContainer", true, false) as Control
@onready var title_line1: Label = find_child("TitleLine1", true, false) as Label
@onready var title_line2: Label = find_child("TitleLine2", true, false) as Label
@onready var title_line3: Label = find_child("TitleLine3", true, false) as Label
@onready var title_rule: ColorRect = find_child("TitleRule", true, false) as ColorRect
@onready var menu_panel: Control = find_child("PanelContainer", true, false) as Control
@onready var start_button: Button = find_child("StartButton", true, false) as Button
@onready var controls_button: Button = find_child("ControlsButton", true, false) as Button
@onready var replay_button: Button = find_child("ReplayButton", true, false) as Button
@onready var quit_button: Button = find_child("QuitButton", true, false) as Button
@onready var controls_dialog: AcceptDialog = find_child("ControlsDialog", true, false) as AcceptDialog


func _ready() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	
	# Connect UI buttons
	if start_button:
		start_button.pressed.connect(_on_start_pressed)
	if controls_button:
		controls_button.pressed.connect(_on_controls_pressed)
	if replay_button:
		replay_button.pressed.connect(_on_replay_pressed)
	if quit_button:
		quit_button.pressed.connect(_on_quit_pressed)
	if skip_button:
		skip_button.pressed.connect(_on_skip_pressed)
		
	# Apply visual enhancements
	var enhancer = load("res://scripts/campus_visual_enhancer.gd").new()
	enhancer.enhance_campus_environment(self)
	enhancer.apply_all_campus_materials(self)
	enhancer.free()
	
	# Initialize intro state
	start_intro_cinematic()


func start_intro_cinematic() -> void:
	current_time = 0.0
	is_skipping = false
	is_menu_active = false
	
	if fade_overlay:
		fade_overlay.modulate.a = 1.0
	if menu_panel:
		menu_panel.modulate.a = 0.0
		menu_panel.visible = false
	if skip_button:
		skip_button.visible = true
		skip_button.modulate.a = 1.0
	if title_container:
		title_container.modulate.a = 0.0
	if title_line1:
		title_line1.modulate.a = 0.0
	if title_line2:
		title_line2.modulate.a = 0.0
	if title_line3:
		title_line3.modulate.a = 0.0
	if title_rule:
		title_rule.modulate.a = 0.0
	if letterbox_top and letterbox_bottom:
		letterbox_top.visible = true
		letterbox_bottom.visible = true

	update_camera_pose(0.0)


func _unhandled_input(event: InputEvent) -> void:
	# Skip intro on Escape, Space, or Enter
	if not is_menu_active and not is_skipping:
		if event.is_action_pressed("ui_cancel") or event.is_action_pressed("jump") or event.is_action_pressed("ui_accept"):
			_on_skip_pressed()


func _process(delta: float) -> void:
	if not is_menu_active:
		current_time += delta
		
		# 1. Evaluate camera fly-through
		update_camera_pose(current_time)
		
		# 2. Fade in from black (0 to 2 seconds)
		if fade_overlay and not is_skipping:
			if current_time < T_FADE_IN:
				fade_overlay.modulate.a = clampf(1.0 - (current_time / T_FADE_IN), 0.0, 1.0)
			else:
				fade_overlay.modulate.a = 0.0
				
		# 3. Title reveal animation (10.0 to 14.0 seconds)
		if title_container:
			if current_time >= 10.0 and current_time < T_MENU:
				title_container.modulate.a = clampf((current_time - 10.0) / 0.8, 0.0, 1.0)
				# Line 1: IMRD
				if title_line1:
					title_line1.modulate.a = clampf((current_time - 10.3) / 1.0, 0.0, 1.0)
				# Rule line
				if title_rule:
					title_rule.modulate.a = clampf((current_time - 11.2) / 0.8, 0.0, 1.0)
				# Line 2: 3D Campus Walkthrough
				if title_line2:
					title_line2.modulate.a = clampf((current_time - 10.9) / 1.0, 0.0, 1.0)
				# Line 3: Institution Name
				if title_line3:
					title_line3.modulate.a = clampf((current_time - 11.5) / 1.0, 0.0, 1.0)
			elif current_time >= T_MENU:
				# Fade out title to make room for menu
				title_container.modulate.a = clampf(1.0 - (current_time - T_MENU) / 1.0, 0.0, 1.0)
				
		# 4. Menu arrival (17 seconds)
		if current_time >= T_MENU and not is_skipping:
			activate_menu()
	else:
		# Keep final camera pose
		update_camera_pose(T_END)


func update_camera_pose(t: float) -> void:
	if not intro_camera:
		return
		
	var clamped_t: float = clampf(t, 0.0, T_END)
	var k_idx: int = 0
	
	for i in range(INTRO_KEYS.size() - 1):
		if clamped_t >= INTRO_KEYS[i]["t"] and clamped_t <= INTRO_KEYS[i + 1]["t"]:
			k_idx = i
			break
			
	var k0: Dictionary = INTRO_KEYS[k_idx]
	var k1: Dictionary = INTRO_KEYS[k_idx + 1]
	
	var dt: float = k1["t"] - k0["t"]
	var s: float = 0.0 if dt <= 0.001 else (clamped_t - k0["t"]) / dt
	
	# Smooth easing
	var weight: float = s
	if k0.get("ease", false) or k1.get("ease", false):
		weight = s * s * (3.0 - 2.0 * s) # smoothstep
		
	var target_pos: Vector3 = (k0["pos"] as Vector3).lerp(k1["pos"] as Vector3, weight)
	var target_look: Vector3 = (k0["look"] as Vector3).lerp(k1["look"] as Vector3, weight)
	
	intro_camera.position = target_pos
	if intro_camera.is_inside_tree():
		intro_camera.look_at(target_look, Vector3.UP)
	else:
		intro_camera.look_at_from_position(target_pos, target_look, Vector3.UP)


func _on_skip_pressed() -> void:
	if is_skipping or is_menu_active:
		return
	is_skipping = true
	
	# Quick cinematic fade transition to menu
	var tween = create_tween()
	tween.tween_property(fade_overlay, "modulate:a", 1.0, 0.25)
	tween.tween_callback(func():
		current_time = T_MENU
		update_camera_pose(T_MENU)
		activate_menu()
		if title_container:
			title_container.modulate.a = 0.0
	)
	tween.tween_property(fade_overlay, "modulate:a", 0.0, 0.35)
	tween.tween_callback(func():
		is_skipping = false
	)


func activate_menu() -> void:
	is_menu_active = true
	if skip_button:
		skip_button.visible = false
	if menu_panel:
		menu_panel.visible = true
		var tween = create_tween()
		tween.tween_property(menu_panel, "modulate:a", 1.0, 0.6)


func _on_replay_pressed() -> void:
	var tween = create_tween()
	tween.tween_property(fade_overlay, "modulate:a", 1.0, 0.3)
	tween.tween_callback(start_intro_cinematic)


func _on_start_pressed() -> void:
	# Fade out and hand over to campus gameplay
	var tween = create_tween()
	tween.tween_property(fade_overlay, "modulate:a", 1.0, 0.5)
	tween.tween_callback(func():
		GameManager.start_game()
	)


func _on_controls_pressed() -> void:
	if controls_dialog:
		controls_dialog.popup_centered()


func _on_quit_pressed() -> void:
	get_tree().quit()
