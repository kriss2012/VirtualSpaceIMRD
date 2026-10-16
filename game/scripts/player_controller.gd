extends CharacterBody3D

@export var walk_speed: float = 6.0
@export var sprint_speed: float = 10.5
@export var jump_velocity: float = 7.0
@export var mouse_sensitivity: float = 0.003
@export var spawn_position: Vector3 = Vector3(0.0, 1.0, -68.0)

var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 18.0)
var camera_pitch: float = 0.0

@onready var camera_pivot: Node3D = $CameraPivot
@onready var spring_arm: SpringArm3D = $CameraPivot/SpringArm3D
@onready var camera: Camera3D = $CameraPivot/SpringArm3D/Camera3D
@onready var visual_mesh: Node3D = $VisualMesh


func _ready() -> void:
	# Position at spawn if starting
	if global_position.length() < 0.1:
		global_position = spawn_position
	# Ensure floor snap and stair climbing
	floor_snap_length = 0.50
	floor_max_angle = deg_to_rad(52.0)
	floor_constant_speed = true


func _unhandled_input(event: InputEvent) -> void:
	if GameManager.current_state != GameManager.GameState.PLAYING:
		return

	# Mouse look
	if event is InputEventMouseMotion:
		rotate_y(-event.relative.x * mouse_sensitivity)
		camera_pitch = clamp(camera_pitch - event.relative.y * mouse_sensitivity, deg_to_rad(-50.0), deg_to_rad(42.0))
		camera_pivot.rotation.x = camera_pitch

	# Interaction Key
	if event.is_action_pressed("interact"):
		if GameManager.active_interactable and GameManager.active_interactable.has_method("interact"):
			GameManager.active_interactable.interact()

	# Pause / Escape
	if event.is_action_pressed("pause"):
		GameManager.toggle_pause()


func _physics_process(delta: float) -> void:
	if GameManager.current_state != GameManager.GameState.PLAYING:
		return

	# Fall detection & safe respawn
	if global_position.y < -10.0:
		global_position = spawn_position
		velocity = Vector3.ZERO
		GameManager.post_notification("Respawned at Campus Entrance.")
		return

	# Apply Gravity
	if not is_on_floor():
		velocity.y -= gravity * delta

	# Jump
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_velocity

	# Movement direction
	var input_dir: Vector2 = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
	var direction: Vector3 = (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()

	var speed: float = sprint_speed if Input.is_action_pressed("sprint") else walk_speed

	if direction:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
		# Smooth visual character rotation toward movement
		if visual_mesh:
			var target_rot = atan2(-direction.x, -direction.z) - rotation.y
			visual_mesh.rotation.y = lerp_angle(visual_mesh.rotation.y, target_rot, delta * 12.0)
	else:
		velocity.x = move_toward(velocity.x, 0, speed * delta * 10.0)
		velocity.z = move_toward(velocity.z, 0, speed * delta * 10.0)

	# Step-up assist for curbs, thresholds, and stairs
	if is_on_wall() and direction.length_squared() > 0.01:
		var step_test = global_transform
		step_test.origin += direction * 0.18 + Vector3(0, 0.32, 0)
		if not test_move(step_test, Vector3.DOWN * 0.30):
			velocity.y = 2.8

	move_and_slide()
