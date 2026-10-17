extends Node3D

@export var room_name: String = "Classroom 101"
@export var is_open: bool = false
@export var open_angle: float = 90.0
@export var swing_speed: float = 4.0

var current_angle: float = 0.0
var target_angle: float = 0.0

@onready var hinge_pivot: Node3D = $HingePivot
@onready var collision_shape: CollisionShape3D = $HingePivot/DoorBody/CollisionShape3D
@onready var sign_label: Label3D = $Signboard/Label3D


func _ready() -> void:
	if not sign_label:
		sign_label = get_node_or_null("Signboard/Label3D")
	if sign_label:
		sign_label.text = room_name
	target_angle = deg_to_rad(open_angle) if is_open else 0.0
	current_angle = target_angle
	apply_rotation(current_angle)
	update_collision()


func _process(delta: float) -> void:
	if abs(current_angle - target_angle) > 0.001:
		current_angle = lerp_angle(current_angle, target_angle, delta * swing_speed)
		apply_rotation(current_angle)


func apply_rotation(ang: float) -> void:
	if not hinge_pivot:
		hinge_pivot = get_node_or_null("HingePivot")
	if hinge_pivot:
		hinge_pivot.rotation.y = ang


func get_interaction_text() -> String:
	return "Press [E] to Close " + room_name if is_open else "Press [E] to Open " + room_name


func interact() -> void:
	is_open = not is_open
	target_angle = deg_to_rad(open_angle) if is_open else 0.0
	update_collision()
	GameManager.set_active_interactable(self, get_interaction_text())
	GameManager.post_notification(room_name + " Door " + ("Opened" if is_open else "Closed"))


func update_collision() -> void:
	if not collision_shape:
		collision_shape = get_node_or_null("HingePivot/DoorBody/CollisionShape3D")
	if collision_shape:
		collision_shape.set_deferred("disabled", is_open)


func _on_interaction_area_body_entered(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.set_active_interactable(self, get_interaction_text())


func _on_interaction_area_body_exited(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.clear_active_interactable(self)
