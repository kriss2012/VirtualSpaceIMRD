extends Node3D

# ==============================================================================
# IMRD 3D Campus Explorer — AAA Gamified Opening & Main Menu System
# Features 3D Cinematic Fly-Through, Tactical Intel Feed, and AAA Settings Suite
# ==============================================================================

# Timeline milestones (seconds)
const T_FADE_IN: float = 2.0
const T_TITLE_START: float = 10.0
const T_MENU: float = 17.0
const T_END: float = 20.0

# Exact camera keyframes from 06_intro_cinematic.py (converted to Godot coordinates)
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

# Main Menu Container & Buttons
@onready var menu_root: Control = find_child("MenuContainer", true, false) as Control
@onready var start_button: Button = find_child("StartButton", true, false) as Button
@onready var continue_button: Button = find_child("ContinueButton", true, false) as Button
@onready var settings_button: Button = find_child("SettingsButton", true, false) as Button
@onready var controls_button: Button = find_child("ControlsButton", true, false) as Button
@onready var replay_button: Button = find_child("ReplayButton", true, false) as Button
@onready var quit_button: Button = find_child("QuitButton", true, false) as Button

# Dynamic Tactical Intel Feed
@onready var intel_title: Label = find_child("IntelTitle", true, false) as Label
@onready var intel_badge: Label = find_child("IntelBadge", true, false) as Label
@onready var intel_desc: Label = find_child("IntelDesc", true, false) as Label
@onready var intel_objective: Label = find_child("IntelObjective", true, false) as Label
@onready var intel_status: Label = find_child("IntelStatus", true, false) as Label
@onready var top_clock_label: Label = find_child("TopClockLabel", true, false) as Label

# Gamified Settings Modal
@onready var settings_modal: Control = find_child("SettingsModal", true, false) as Control
@onready var tab_graphics_btn: Button = find_child("TabGraphicsBtn", true, false) as Button
@onready var tab_audio_btn: Button = find_child("TabAudioBtn", true, false) as Button
@onready var tab_controls_btn: Button = find_child("TabControlsBtn", true, false) as Button
@onready var panel_graphics: Control = find_child("PanelGraphics", true, false) as Control
@onready var panel_audio: Control = find_child("PanelAudio", true, false) as Control
@onready var panel_controls: Control = find_child("PanelControls", true, false) as Control

# Settings Inputs
@onready var check_fullscreen: CheckButton = find_child("CheckFullscreen", true, false) as CheckButton
@onready var opt_resolution: OptionButton = find_child("OptResolution", true, false) as OptionButton
@onready var check_shadows: CheckButton = find_child("CheckShadows", true, false) as CheckButton
@onready var check_ssao: CheckButton = find_child("CheckSSAO", true, false) as CheckButton
@onready var check_glow: CheckButton = find_child("CheckGlow", true, false) as CheckButton
@onready var check_vsync: CheckButton = find_child("CheckVSync", true, false) as CheckButton

@onready var slider_master: HSlider = find_child("SliderMaster", true, false) as HSlider
@onready var lbl_master_val: Label = find_child("LblMasterVal", true, false) as Label
@onready var slider_music: HSlider = find_child("SliderMusic", true, false) as HSlider
@onready var lbl_music_val: Label = find_child("LblMusicVal", true, false) as Label
@onready var slider_sfx: HSlider = find_child("SliderSFX", true, false) as HSlider
@onready var lbl_sfx_val: Label = find_child("LblSFXVal", true, false) as Label
@onready var check_ui_sound: CheckButton = find_child("CheckUISound", true, false) as CheckButton

@onready var slider_sens: HSlider = find_child("SliderSens", true, false) as HSlider
@onready var lbl_sens_val: Label = find_child("LblSensVal", true, false) as Label
@onready var check_invert_y: CheckButton = find_child("CheckInvertY", true, false) as CheckButton
@onready var slider_fov: HSlider = find_child("SliderFOV", true, false) as HSlider
@onready var lbl_fov_val: Label = find_child("LblFOVVal", true, false) as Label

@onready var btn_settings_apply: Button = find_child("BtnSettingsApply", true, false) as Button
@onready var btn_settings_reset: Button = find_child("BtnSettingsReset", true, false) as Button
@onready var btn_settings_close: Button = find_child("BtnSettingsClose", true, false) as Button

# Controls & Guide Modal
@onready var controls_modal: Control = find_child("ControlsModal", true, false) as Control
@onready var btn_controls_close: Button = find_child("BtnControlsClose", true, false) as Button
@onready var controls_dialog: AcceptDialog = find_child("ControlsDialog", true, false) as AcceptDialog


func _ready() -> void:
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	
	_connect_main_buttons()
	_connect_settings_controls()
	_update_save_state_ui()
	
	# Apply visual enhancements to 3D campus backdrop
	var enhancer = load("res://scripts/campus_visual_enhancer.gd").new()
	enhancer.enhance_campus_environment(self)
	enhancer.apply_all_campus_materials(self)
	enhancer.free()
	
	# Initialize intro state
	start_intro_cinematic()


func _connect_main_buttons() -> void:
	if start_button:
		start_button.pressed.connect(_on_start_pressed)
		start_button.mouse_entered.connect(func(): _on_button_hovered("start"))
	if continue_button:
		continue_button.pressed.connect(_on_continue_pressed)
		continue_button.mouse_entered.connect(func(): _on_button_hovered("continue"))
	if settings_button:
		settings_button.pressed.connect(_on_settings_pressed)
		settings_button.mouse_entered.connect(func(): _on_button_hovered("settings"))
	if controls_button:
		controls_button.pressed.connect(_on_controls_pressed)
		controls_button.mouse_entered.connect(func(): _on_button_hovered("controls"))
	if replay_button:
		replay_button.pressed.connect(_on_replay_pressed)
		replay_button.mouse_entered.connect(func(): _on_button_hovered("replay"))
	if quit_button:
		quit_button.pressed.connect(_on_quit_pressed)
		quit_button.mouse_entered.connect(func(): _on_button_hovered("quit"))
	if skip_button:
		skip_button.pressed.connect(_on_skip_pressed)
	if btn_controls_close:
		btn_controls_close.pressed.connect(_on_controls_close_pressed)


func _connect_settings_controls() -> void:
	if tab_graphics_btn:
		tab_graphics_btn.pressed.connect(func(): _switch_settings_tab(0))
	if tab_audio_btn:
		tab_audio_btn.pressed.connect(func(): _switch_settings_tab(1))
	if tab_controls_btn:
		tab_controls_btn.pressed.connect(func(): _switch_settings_tab(2))
		
	if slider_master:
		slider_master.value_changed.connect(func(v):
			if lbl_master_val: lbl_master_val.text = "%d%%" % int(v * 100.0)
		)
	if slider_music:
		slider_music.value_changed.connect(func(v):
			if lbl_music_val: lbl_music_val.text = "%d%%" % int(v * 100.0)
		)
	if slider_sfx:
		slider_sfx.value_changed.connect(func(v):
			if lbl_sfx_val: lbl_sfx_val.text = "%d%%" % int(v * 100.0)
		)
	if slider_sens:
		slider_sens.value_changed.connect(func(v):
			if lbl_sens_val: lbl_sens_val.text = "%.1fx" % v
		)
	if slider_fov:
		slider_fov.value_changed.connect(func(v):
			if lbl_fov_val: lbl_fov_val.text = "%d°" % int(v)
		)
		
	if btn_settings_apply:
		btn_settings_apply.pressed.connect(_on_settings_apply_pressed)
	if btn_settings_reset:
		btn_settings_reset.pressed.connect(_on_settings_reset_pressed)
	if btn_settings_close:
		btn_settings_close.pressed.connect(_on_settings_close_pressed)


func _update_save_state_ui() -> void:
	var has_save: bool = SaveManager.has_save()
	if continue_button:
		continue_button.disabled = not has_save
		if has_save:
			continue_button.text = "▶ [ 02 ]  CONTINUE JOURNEY (RESUME)"
		else:
			continue_button.text = "  [ 02 ]  CONTINUE (NO SAVE DATA)"


func start_intro_cinematic() -> void:
	current_time = 0.0
	is_skipping = false
	is_menu_active = false
	
	if fade_overlay:
		fade_overlay.modulate.a = 1.0
	if menu_root:
		menu_root.modulate.a = 0.0
		menu_root.visible = false
	if settings_modal:
		settings_modal.visible = false
	if controls_modal:
		controls_modal.visible = false
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
	elif is_menu_active:
		if event.is_action_pressed("ui_cancel"):
			if settings_modal and settings_modal.visible:
				_on_settings_close_pressed()
			elif controls_modal and controls_modal.visible:
				_on_controls_close_pressed()


func _process(delta: float) -> void:
	# Update top system clock
	if top_clock_label:
		top_clock_label.text = "SYSTEM CLOCK: %s // STATUS: NORMAL" % Time.get_time_string_from_system()

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
				if title_line1:
					title_line1.modulate.a = clampf((current_time - 10.3) / 1.0, 0.0, 1.0)
				if title_rule:
					title_rule.modulate.a = clampf((current_time - 11.2) / 0.8, 0.0, 1.0)
				if title_line2:
					title_line2.modulate.a = clampf((current_time - 10.9) / 1.0, 0.0, 1.0)
				if title_line3:
					title_line3.modulate.a = clampf((current_time - 11.5) / 1.0, 0.0, 1.0)
			elif current_time >= T_MENU:
				title_container.modulate.a = clampf(1.0 - (current_time - T_MENU) / 1.0, 0.0, 1.0)
				
		# 4. Menu arrival (17 seconds)
		if current_time >= T_MENU and not is_skipping:
			activate_menu()
	else:
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
	
	var weight: float = s
	if k0.get("ease", false) or k1.get("ease", false):
		weight = s * s * (3.0 - 2.0 * s)
		
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
	GameManager.play_ui_sound("click")
	
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
	if menu_root:
		menu_root.visible = true
		var tween = create_tween()
		tween.tween_property(menu_root, "modulate:a", 1.0, 0.6)
	_on_button_hovered("start")


func _on_button_hovered(type: String) -> void:
	if not is_menu_active:
		return
	GameManager.play_ui_sound("hover")
	
	match type:
		"start":
			if intel_badge: intel_badge.text = "[ BRIEFING // NEW STUDENT INDUCTION ]"
			if intel_title: intel_title.text = "CAMPUS EXPLORATION: ACTIVE"
			if intel_desc: intel_desc.text = "Begin your academic journey at the main boulevard gates. Explore the ground floor entrance plinth, double doors, classrooms, and meet Prof. Sharma."
			if intel_objective: intel_objective.text = "PRIMARY DIRECTIVE:\n• Report to Faculty Guide Prof. Sharma at the entrance plaza\n• Locate and recover your missing Student ID Card\n• Explore all 3 designated campus sectors"
			if intel_status: intel_status.text = "STATUS: READY TO DEPLOY"
		"continue":
			if intel_badge: intel_badge.text = "[ DOSSIER // RESUME SAVED DATA ]"
			if intel_title: intel_title.text = "ACADEMIC ARCHIVE RECOVERY"
			var has_save = SaveManager.has_save()
			if has_save:
				if intel_desc: intel_desc.text = "Valid local save record detected in encrypted storage. You will restore your previous character location, mission objectives, and collected ID inventory."
				if intel_objective: intel_objective.text = "SAVED DATA SUMMARY:\n• Student Level: %d\n• Earned XP: %d XP\n• Missions in Progress: 3" % [MissionManager.level, MissionManager.xp]
				if intel_status: intel_status.text = "STATUS: SAVE VALIDATED & READY"
			else:
				if intel_desc: intel_desc.text = "No saved walkthrough record located in local storage. Start a new session from the gates to initialize your student dossier."
				if intel_objective: intel_objective.text = "SYSTEM NOTICE:\n• No previous checkpoint on disk\n• Select [START WALKTHROUGH] to begin"
				if intel_status: intel_status.text = "STATUS: NO SAVE FILE"
		"settings":
			if intel_badge: intel_badge.text = "[ CONFIG // ENGINE CALIBRATION ]"
			if intel_title: intel_title.text = "HARDWARE & SIMULATION SETTINGS"
			if intel_desc: intel_desc.text = "Calibrate rendering parameters, ambient lighting, shadows, screen resolution, master audio channels, and mouse look sensitivity."
			if intel_objective: intel_objective.text = "ACTIVE PREFERENCES:\n• Resolution: %s\n• Window Mode: %s\n• Ambient Occlusion & Shadows: High Quality" % [
				"1280x720" if GameManager.settings.get("resolution_index", 0) == 0 else "1920x1080",
				"Fullscreen" if GameManager.settings.get("fullscreen", false) else "Windowed"
			]
			if intel_status: intel_status.text = "STATUS: ENGINE CALIBRATED"
		"controls":
			if intel_badge: intel_badge.text = "[ DIRECTORY // CAMPUS ATLAS & GUIDE ]"
			if intel_title: intel_title.text = "TACTICAL INTERACTION MANUAL"
			if intel_desc: intel_desc.text = "Review keybindings, character navigation, interactive door systems, and the complete floor plan directory for classrooms and halls."
			if intel_objective: intel_objective.text = "QUICK KEYS:\n• Movement: [W, A, S, D] | Sprint: [SHIFT]\n• Interact: [E] | Jump: [SPACEBAR]\n• Pause & Settings: [ESC / Q]"
			if intel_status: intel_status.text = "STATUS: MANUAL READY"
		"replay":
			if intel_badge: intel_badge.text = "[ SURVEILLANCE // DRONE OVERVIEW ]"
			if intel_title: intel_title.text = "AERIAL CAMPUS CINEMATIC"
			if intel_desc: intel_desc.text = "Re-launch the 20-second dynamic aerial fly-through tracking across the gate, boulevard, portico, and main academic building."
			if intel_objective: intel_objective.text = "DRONE FLIGHT ROUTE:\n• Main Boulevard Gate (Z = -90m)\n• Boulevard Fly-over (Z = -56m)\n• Entrance Portico Arrival (Z = -21m)"
			if intel_status: intel_status.text = "STATUS: FLIGHT READY"
		"quit":
			if intel_badge: intel_badge.text = "[ SYSTEM // TERMINATE SIMULATION ]"
			if intel_title: intel_title.text = "SHUT DOWN RUNTIME"
			if intel_desc: intel_desc.text = "Save your system parameters and safely terminate the 3D game engine, returning directly to your Windows desktop."
			if intel_objective: intel_objective.text = "SESSION SHUTDOWN:\n• All settings will be preserved\n• Auto-save will store active mission states"
			if intel_status: intel_status.text = "STATUS: CONFIRM EXIT"


func _on_start_pressed() -> void:
	GameManager.play_ui_sound("click")
	var tween = create_tween()
	tween.tween_property(fade_overlay, "modulate:a", 1.0, 0.5)
	tween.tween_callback(func():
		GameManager.start_game()
	)


func _on_continue_pressed() -> void:
	if not SaveManager.has_save():
		GameManager.play_ui_sound("back")
		return
	GameManager.play_ui_sound("click")
	var tween = create_tween()
	tween.tween_property(fade_overlay, "modulate:a", 1.0, 0.5)
	tween.tween_callback(func():
		SaveManager.load_game()
		GameManager.start_game()
	)


func _on_settings_pressed() -> void:
	GameManager.play_ui_sound("click")
	_populate_settings_ui()
	_switch_settings_tab(0)
	if settings_modal:
		settings_modal.visible = true
		settings_modal.modulate.a = 0.0
		var tween = create_tween()
		tween.tween_property(settings_modal, "modulate:a", 1.0, 0.25)


func _populate_settings_ui() -> void:
	var s = GameManager.settings
	if check_fullscreen:
		check_fullscreen.button_pressed = s.get("fullscreen", false)
	if opt_resolution:
		opt_resolution.selected = s.get("resolution_index", 0)
	if check_shadows:
		check_shadows.button_pressed = s.get("shadows", true)
	if check_ssao:
		check_ssao.button_pressed = s.get("ssao", true)
	if check_glow:
		check_glow.button_pressed = s.get("glow", true)
	if check_vsync:
		check_vsync.button_pressed = s.get("vsync", true)
		
	if slider_master:
		slider_master.value = s.get("master_volume", 1.0)
		if lbl_master_val: lbl_master_val.text = "%d%%" % int(slider_master.value * 100.0)
	if slider_music:
		slider_music.value = s.get("music_volume", 0.8)
		if lbl_music_val: lbl_music_val.text = "%d%%" % int(slider_music.value * 100.0)
	if slider_sfx:
		slider_sfx.value = s.get("sfx_volume", 0.9)
		if lbl_sfx_val: lbl_sfx_val.text = "%d%%" % int(slider_sfx.value * 100.0)
	if check_ui_sound:
		check_ui_sound.button_pressed = s.get("ui_sound", true)
		
	if slider_sens:
		slider_sens.value = s.get("mouse_sensitivity", 1.0)
		if lbl_sens_val: lbl_sens_val.text = "%.1fx" % slider_sens.value
	if check_invert_y:
		check_invert_y.button_pressed = s.get("invert_y", false)
	if slider_fov:
		slider_fov.value = s.get("fov", 70.0)
		if lbl_fov_val: lbl_fov_val.text = "%d°" % int(slider_fov.value)


func _switch_settings_tab(idx: int) -> void:
	GameManager.play_ui_sound("toggle")
	if panel_graphics: panel_graphics.visible = (idx == 0)
	if panel_audio: panel_audio.visible = (idx == 1)
	if panel_controls: panel_controls.visible = (idx == 2)


func _on_settings_apply_pressed() -> void:
	var s = GameManager.settings
	if check_fullscreen: s["fullscreen"] = check_fullscreen.button_pressed
	if opt_resolution: s["resolution_index"] = opt_resolution.selected
	if check_shadows: s["shadows"] = check_shadows.button_pressed
	if check_ssao: s["ssao"] = check_ssao.button_pressed
	if check_glow: s["glow"] = check_glow.button_pressed
	if check_vsync: s["vsync"] = check_vsync.button_pressed
	
	if slider_master: s["master_volume"] = slider_master.value
	if slider_music: s["music_volume"] = slider_music.value
	if slider_sfx: s["sfx_volume"] = slider_sfx.value
	if check_ui_sound: s["ui_sound"] = check_ui_sound.button_pressed
	
	if slider_sens: s["mouse_sensitivity"] = slider_sens.value
	if check_invert_y: s["invert_y"] = check_invert_y.button_pressed
	if slider_fov: s["fov"] = slider_fov.value
	
	GameManager.save_settings()
	GameManager.apply_settings()
	GameManager.play_ui_sound("click")
	
	# Close modal
	_on_settings_close_pressed()


func _on_settings_reset_pressed() -> void:
	GameManager.settings = {
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
	GameManager.save_settings()
	GameManager.apply_settings()
	_populate_settings_ui()
	GameManager.play_ui_sound("toggle")


func _on_settings_close_pressed() -> void:
	GameManager.play_ui_sound("back")
	if settings_modal:
		var tween = create_tween()
		tween.tween_property(settings_modal, "modulate:a", 0.0, 0.2)
		tween.tween_callback(func(): settings_modal.visible = false)


func _on_controls_pressed() -> void:
	GameManager.play_ui_sound("click")
	if controls_modal:
		controls_modal.visible = true
		controls_modal.modulate.a = 0.0
		var tween = create_tween()
		tween.tween_property(controls_modal, "modulate:a", 1.0, 0.25)


func _on_controls_close_pressed() -> void:
	GameManager.play_ui_sound("back")
	if controls_modal:
		var tween = create_tween()
		tween.tween_property(controls_modal, "modulate:a", 0.0, 0.2)
		tween.tween_callback(func(): controls_modal.visible = false)


func _on_replay_pressed() -> void:
	GameManager.play_ui_sound("click")
	var tween = create_tween()
	tween.tween_property(fade_overlay, "modulate:a", 1.0, 0.3)
	tween.tween_callback(start_intro_cinematic)


func _on_quit_pressed() -> void:
	GameManager.play_ui_sound("click")
	get_tree().quit()
