"""
04_missions.py
==============
Data-Driven Mission and Progression System for IMRD Campus Game.
Implements:
- Objectives, state machine (NOT_STARTED, ACTIVE, COMPLETED).
- Missions:
  1. "First Day at IMRD" (Meet Prof. Sharma).
  2. "Campus Explorer" (Visit Reception, Ground Classroom, 1st Floor, Garden, Parking).
  3. "The Lost ID Card" (Find golden ID card in garden and return it).
- XP, Leveling (1 to 10), Achievements, and Inventory management.
- JSON-based save and restore progress.
"""

import json
from pathlib import Path

# Mathutils / Vector fallback for standalone execution
try:
    from mathutils import Vector
except ImportError:
    class Vector(tuple):
        def __new__(cls, coords):
            return super().__new__(cls, tuple(coords))
        @property
        def x(self): return self[0]
        @property
        def y(self): return self[1]
        @property
        def z(self): return self[2]
        @property
        def length(self):
            return (self[0]**2 + self[1]**2 + self[2]**2) ** 0.5
        def __sub__(self, other):
            return Vector((self[0] - other[0], self[1] - other[1], self[2] - other[2]))

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SAVE_FILE = OUTPUT_DIR / "game_save.json"

class MissionManager:
    def __init__(self):
        self.xp = 0
        self.level = 1
        self.inventory = []
        self.achievements = []
        self.visited_zones = set()

        # Exploration Zones
        self.EXPLORATION_ZONES = {
            "Entrance_Plaza": {"pos": Vector((0, 16, 0)), "radius": 8.0, "visited": False},
            "Reception_Lobby": {"pos": Vector((-3.5, 4, 0.3)), "radius": 4.5, "visited": False},
            "Ground_Classroom": {"pos": Vector((-14, 4.5, 0.3)), "radius": 5.5, "visited": False},
            "First_Floor": {"pos": Vector((0, 2, 4.3)), "radius": 6.0, "visited": False},
            "Campus_Garden": {"pos": Vector((-40, 48.5, 0)), "radius": 9.0, "visited": False},
            "Parking_Lot": {"pos": Vector((44, 43, 0)), "radius": 12.0, "visited": False},
            "Seminar_Hall": {"pos": Vector((14.2, 4.2, 4.3)), "radius": 6.0, "visited": False},
            "Academic_Library": {"pos": Vector((0.0, -4.2, 4.3)), "radius": 6.0, "visited": False},
            "Badminton_Court": {"pos": Vector((38.0, 5.0, 0.0)), "radius": 7.0, "visited": False},
            "Bike_Station": {"pos": Vector((24.0, 49.0, 0.0)), "radius": 5.0, "visited": False},
        }

        # Data-driven missions
        self.missions = {
            "first_day": {
                "title": "First Day at IMRD",
                "desc": "Speak with Campus Guide Prof. Sharma at the entrance plaza.",
                "state": "ACTIVE",
                "xp_reward": 150,
                "completed": False
            },
            "campus_explorer": {
                "title": "Campus Explorer",
                "desc": "Discover all 6 key areas of the IMRD campus.",
                "state": "ACTIVE",
                "required_zones": 6,
                "current_zones": 0,
                "xp_reward": 300,
                "completed": False
            },
            "lost_id_card": {
                "title": "The Lost ID Card",
                "desc": "Locate the lost golden Student ID card in the garden and return it.",
                "state": "NOT_STARTED",
                "has_card": False,
                "returned": False,
                "xp_reward": 400,
                "completed": False
            }
        }

    def add_xp(self, amount, reason=""):
        self.xp += amount
        new_level = (self.xp // 250) + 1
        leveled_up = new_level > self.level
        self.level = new_level
        msg = f"[XP +{amount}] {reason}"
        if leveled_up:
            msg += f" | LEVEL UP! You are now Level {self.level}!"
            self.achievements.append(f"Reached Level {self.level}")
        print(msg)
        return msg

    def update_player_location(self, player_pos):
        """Checks if player discovered any exploration zones."""
        p_vec = Vector((player_pos.x, player_pos.y, player_pos.z))
        notifications = []

        for zone_name, data in self.EXPLORATION_ZONES.items():
            if not data["visited"]:
                dist = (Vector((p_vec.x, p_vec.y, 0)) - Vector((data["pos"].x, data["pos"].y, 0))).length
                if dist <= data["radius"]:
                    data["visited"] = True
                    self.visited_zones.add(zone_name)
                    clean_name = zone_name.replace("_", " ")
                    notif = f"Discovered Location: {clean_name}!"
                    notifications.append(notif)
                    self.add_xp(50, f"Discovered {clean_name}")

                    # Update Campus Explorer mission
                    m_exp = self.missions["campus_explorer"]
                    m_exp["current_zones"] = len(self.visited_zones)
                    if m_exp["current_zones"] >= m_exp["required_zones"] and not m_exp["completed"]:
                        m_exp["completed"] = True
                        m_exp["state"] = "COMPLETED"
                        self.add_xp(m_exp["xp_reward"], "Completed Mission: Campus Explorer")
                        self.achievements.append("Campus Cartographer")
                        notifications.append("[ACHIEVEMENT UNLOCKED] Campus Cartographer!")

        return notifications

    def on_talk_to_guide(self):
        """Called when player interacts with Prof. Sharma."""
        notifications = []
        m_fd = self.missions["first_day"]
        if not m_fd["completed"]:
            m_fd["completed"] = True
            m_fd["state"] = "COMPLETED"
            self.add_xp(m_fd["xp_reward"], "Completed Mission: First Day at IMRD")
            self.achievements.append("IMRD Fresher")
            notifications.append("[MISSION COMPLETE] First Day at IMRD (+150 XP)")
            # Unlock Lost ID Card mission
            self.missions["lost_id_card"]["state"] = "ACTIVE"
            notifications.append("[NEW MISSION] The Lost ID Card: Search the garden!")

        # Check if returning lost card
        m_card = self.missions["lost_id_card"]
        if m_card["has_card"] and not m_card["returned"]:
            m_card["returned"] = True
            m_card["completed"] = True
            m_card["state"] = "COMPLETED"
            self.inventory.remove("Student ID Card (Roll #2026-MCA-042)")
            self.add_xp(m_card["xp_reward"], "Returned Lost Student ID Card")
            self.achievements.append("Campus Hero")
            notifications.append("[MISSION COMPLETE] The Lost ID Card (+400 XP)!")
            notifications.append("[ACHIEVEMENT UNLOCKED] Campus Hero!")

        return notifications

    def on_pickup_id_card(self):
        """Called when player picks up the card in garden."""
        notifications = []
        m_card = self.missions["lost_id_card"]
        if not m_card["has_card"]:
            m_card["has_card"] = True
            m_card["state"] = "ACTIVE"
            self.inventory.append("Student ID Card (Roll #2026-MCA-042)")
            self.add_xp(200, "Found Lost ID Card")
            notifications.append("[ITEM ACQUIRED] Student ID Card (Roll #2026-MCA-042)")
            notifications.append("Objective Updated: Return the ID card to Prof. Sharma at the entrance plaza.")
        return notifications

    def get_current_objective_text(self):
        """Returns single-line summary of current active objective for HUD."""
        for m_id, m in self.missions.items():
            if m["state"] == "ACTIVE":
                if m_id == "first_day":
                    return "MISSION: First Day at IMRD - Talk to Prof. Sharma at Entrance Plaza"
                elif m_id == "campus_explorer":
                    return f"MISSION: Campus Explorer - Discover key locations ({m['current_zones']}/{m['required_zones']})"
                elif m_id == "lost_id_card":
                    if not m["has_card"]:
                        return "MISSION: The Lost ID Card - Search the garden for the golden card"
                    else:
                        return "MISSION: The Lost ID Card - Return the card to Prof. Sharma"
        return "ALL MISSIONS COMPLETE! You are a graduate of IMRD Campus!"

    def save_state(self, filepath=SAVE_FILE):
        data = {
            "xp": self.xp,
            "level": self.level,
            "inventory": self.inventory,
            "achievements": self.achievements,
            "visited_zones": list(self.visited_zones),
            "missions": self.missions
        }
        Path(filepath).write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"[Mission System] Saved game state to: {filepath}")

    def load_state(self, filepath=SAVE_FILE):
        p = Path(filepath)
        if not p.exists():
            return False
        data = json.loads(p.read_text(encoding="utf-8"))
        self.xp = data.get("xp", 0)
        self.level = data.get("level", 1)
        self.inventory = data.get("inventory", [])
        self.achievements = data.get("achievements", [])
        self.visited_zones = set(data.get("visited_zones", []))
        self.missions = data.get("missions", self.missions)
        print(f"[Mission System] Loaded game state from: {filepath}")
        return True

# Standalone test
if __name__ == "__main__":
    mgr = MissionManager()
    print("Initial status:", mgr.get_current_objective_text())
    # Simulate meeting guide
    mgr.on_talk_to_guide()
    # Simulate exploring garden
    mgr.update_player_location(Vector((-40, 48.5, 0)))
    # Simulate picking up ID card
    mgr.on_pickup_id_card()
    print("Active objective:", mgr.get_current_objective_text())
    # Save test
    mgr.save_state()
    print(f"XP: {mgr.xp} | Level: {mgr.level} | Inventory: {mgr.inventory} | Achievements: {mgr.achievements}")
