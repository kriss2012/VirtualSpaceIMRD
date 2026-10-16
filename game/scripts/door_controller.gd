extends Node3D

@export var door_id: String = "door_main"
@export var open_angle_degrees: float = 90.0
@export var animation_speed: float = 4.0
@export var is_open: bool = false

var target_rotation_y: float = 0.0
var current_rotation_y: float = 0.0

@onready var hinge_pivot: Node3D = $HingePivot
@onready var collision_shape: CollisionShape3D = $HingePivot/DoorBody/CollisionShape3D


func _ready() -> void:
	target_rotation_y = deg_to_rad(open_angle_degrees) if is_open else 0.0
	current_rotation_y = target_rotation_y
	if hinge_pivot:
		hinge_pivot.rotation.y = current_rotation_y


func _process(delta: float) -> void:
	if hinge_pivot and abs(current_rotation_y - target_rotation_y) > 0.005:
		current_rotation_y = lerp_angle(current_rotation_y, target_rotation_y, delta * animation_speed)
		hinge_pivot.rotation.y = current_rotation_y


func get_interaction_text() -> String:
	return "Press [E] to Close Door" if is_open else "Press [E] to Open Door"


func interact() -> void:
	is_open = !is_open
	target_rotation_y = deg_to_rad(open_angle_degrees) if is_open else 0.0
	var state_text = "Opened" if is_open else "Closed"
	GameManager.post_notification("Door " + state_text + ".")
	GameManager.set_active_interactable(self, get_interaction_text())


func _on_interaction_area_body_entered(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.set_active_interactable(self, get_interaction_text())


func _on_interaction_area_body_exited(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.clear_active_interactable(self)
