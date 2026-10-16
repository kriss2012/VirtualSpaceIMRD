extends Node3D

var time_passed: float = 0.0
var base_y: float = 0.0
var is_collected: bool = false


func _ready() -> void:
	base_y = position.y
	# Check if already collected in current save
	if MissionManager.missions["lost_id_card"]["has_card"]:
		queue_free()


func _process(delta: float) -> void:
	if is_collected:
		return
	time_passed += delta
	# Subtle hover bobbing and rotation
	position.y = base_y + sin(time_passed * 3.0) * 0.08
	rotation.y += delta * 1.5


func get_interaction_text() -> String:
	return "Press [E] to Pick Up Student ID Card"


func interact() -> void:
	if is_collected:
		return
	is_collected = true
	var notifs = MissionManager.on_pickup_id_card()
	for n in notifs:
		GameManager.post_notification(n)
	GameManager.clear_active_interactable(self)
	queue_free()


func _on_interaction_area_body_entered(body: Node3D) -> void:
	if is_collected:
		return
	if body.is_in_group("player") or body.name == "Player":
		GameManager.set_active_interactable(self, get_interaction_text())


func _on_interaction_area_body_exited(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		GameManager.clear_active_interactable(self)
