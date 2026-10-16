extends CharacterBody3D

@export var npc_name: String = "Prof. Sharma"
@export var npc_role: String = "Campus Guide"

var player_ref: Node3D = null
var dialogue_lines: Array = [
	"Namaste! Welcome to RCPET's Institute of Management Research and Development (IMRD), Shirpur!",
	"I am Prof. Sharma, your campus guide. We are delighted to have you here today.",
	"Before you begin, please check the entrance walkway—a student reportedly dropped their ID Card near the zebra crossing!",
	"Collect your card and take a tour through the Ground Floor Classrooms, Grand Lobby, and Garden Courtyard. Best of luck!"
]


func _ready() -> void:
	pass


func _process(delta: float) -> void:
	# Smoothly turn toward player when talking or nearby
	if player_ref and is_instance_valid(player_ref):
		var target_pos = player_ref.global_position
		target_pos.y = global_position.y
		var look_dir = (target_pos - global_position).normalized()
		if look_dir.length_squared() > 0.01:
			var target_rot = atan2(look_dir.x, look_dir.z)
			rotation.y = lerp_angle(rotation.y, target_rot, delta * 4.0)


func get_interaction_text() -> String:
	return "Press [E] to Talk to " + npc_name


func interact() -> void:
	var notifs = MissionManager.on_talk_to_guide()
	for n in notifs:
		GameManager.post_notification(n)
	GameManager.trigger_dialogue(npc_name + " (" + npc_role + ")", dialogue_lines)


func _on_interaction_area_body_entered(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		player_ref = body
		GameManager.set_active_interactable(self, get_interaction_text())


func _on_interaction_area_body_exited(body: Node3D) -> void:
	if body.is_in_group("player") or body.name == "Player":
		player_ref = null
		GameManager.clear_active_interactable(self)
