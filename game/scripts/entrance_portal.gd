extends Node3D

@export var is_open: bool = false
@export var open_angle: float = 95.0
@export var swing_speed: float = 4.0

var current_angle: float = 0.0
var target_angle: float = 0.0

@onready var hinge_left: Node3D = $HingeLeft
@onready var hinge_right: Node3D = $HingeRight
@onready var collision_left: CollisionShape3D = $HingeLeft/DoorBodyLeft/CollisionShape3D
@onready var collision_right: CollisionShape3D = $HingeRight/DoorBodyRight/CollisionShape3D


func _ready() -> void:
	target_angle = deg_to_rad(open_angle) if is_open else 0.0
	current_angle = target_angle
	apply_rotation(current_angle)
	update_collision()


func _process(delta: float) -> void:
	if abs(current_angle - target_angle) > 0.001:
		current_angle = lerp_angle(current_angle, target_angle, delta * swing_speed)
		apply_rotation(current_angle)


func apply_rotation(ang: float) -> void:
	# Left door swings outward to the left (negative Y rotation)
	# Right door swings outward to the right (positive Y rotation)
	if hinge_left:
		hinge_left.rotation.y = -ang
	if hinge_right:
		hinge_right.rotation.y = ang


func get_interaction_text() -> String:
	return "Press [E] to Close Main Entrance" if is_open else "Press [E] to Open Main Entrance"


func interact() -> void:
	is_open = not is_open
	target_angle = deg_to_rad(open_angle) if is_open else 0.0
	update_collision()
	GameManager.set_active_interactable(self, get_interaction_text())
	GameManager.post_notification("Main Entrance Doors " + ("Opened" if is_open else "Closed"))


func update_collision() -> void:
	# When doors are open, disable door body collision so player walks through freely
	if collision_left:
		collision_left.disabled = is_open
	if collision_right:
		collision_right.disabled = is_open


func _on_interaction_area_body_entered(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.set_active_interactable(self, get_interaction_text())


func _on_interaction_area_body_exited(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.clear_active_interactable(self)
