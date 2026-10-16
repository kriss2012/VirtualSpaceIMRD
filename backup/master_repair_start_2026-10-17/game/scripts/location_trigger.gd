extends Area3D

@export var location_id: String = "classroom"


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		MissionManager.on_visit_location(location_id)
