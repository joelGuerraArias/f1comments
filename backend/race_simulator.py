import json
import random
from typing import List, Dict

# Complete 2026 Roster with URLs mapped to TLA (22 pilotos oficiales 2026)
DRIVERS_2026 = [
    {"Tla": "ALB", "FullName": "Alexander Albon", "TeamName": "Williams"},
    {"Tla": "ALO", "FullName": "Fernando Alonso", "TeamName": "Aston Martin"},
    {"Tla": "ANT", "FullName": "Kimi Antonelli", "TeamName": "Mercedes"},
    {"Tla": "BEA", "FullName": "Oliver Bearman", "TeamName": "Haas"},
    {"Tla": "BOR", "FullName": "Gabriel Bortoleto", "TeamName": "Audi"},
    {"Tla": "BOT", "FullName": "Valtteri Bottas", "TeamName": "Cadillac"},
    {"Tla": "COL", "FullName": "Franco Colapinto", "TeamName": "Alpine"},
    {"Tla": "GAS", "FullName": "Pierre Gasly", "TeamName": "Alpine"},
    {"Tla": "HAD", "FullName": "Isack Hadjar", "TeamName": "Racing Bulls"},
    {"Tla": "HAM", "FullName": "Lewis Hamilton", "TeamName": "Ferrari"},
    {"Tla": "HUL", "FullName": "Nico Hulkenberg", "TeamName": "Audi"},
    {"Tla": "LAW", "FullName": "Liam Lawson", "TeamName": "Red Bull Racing"},
    {"Tla": "LEC", "FullName": "Charles Leclerc", "TeamName": "Ferrari"},
    {"Tla": "LIN", "FullName": "Arvid Lindblad", "TeamName": "Racing Bulls"},
    {"Tla": "NOR", "FullName": "Lando Norris", "TeamName": "McLaren"},
    {"Tla": "OCO", "FullName": "Esteban Ocon", "TeamName": "Haas"},
    {"Tla": "PER", "FullName": "Sergio Perez", "TeamName": "Cadillac"},
    {"Tla": "PIA", "FullName": "Oscar Piastri", "TeamName": "McLaren"},
    {"Tla": "RUS", "FullName": "George Russell", "TeamName": "Mercedes"},
    {"Tla": "SAI", "FullName": "Carlos Sainz", "TeamName": "Williams"},
    {"Tla": "STR", "FullName": "Lance Stroll", "TeamName": "Aston Martin"},
    {"Tla": "VER", "FullName": "Max Verstappen", "TeamName": "Red Bull Racing"},
]

def generate_driver_url(tla: str, first_name: str, last_name: str, team_name: str) -> str:
    """Generate the URL for the driver using requested format, with overrides for RBR."""
    # RED BULL OVERRIDES
    if tla == "VER":
        return "https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2025/redbullracing/maxver01/2025redbullracingmaxver01right.webp"
    if tla == "HAD":
        return "https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2026/redbullracing/isahad01/2026redbullracingisahad01right.webp"

    team_slug = team_name.lower().replace(" ", "").replace("racing", "").replace("f1team", "").replace("kick", "")
    if team_slug == "redbull": team_slug = "redbullracing"
    elif team_slug == "astonmartin": team_slug = "astonmartin"
    elif team_slug == "haas": team_slug = "haas"
    elif team_slug == "rb": team_slug = "rb"
    elif team_slug == "sauber": team_slug = "kicksauber"

    name_slug = (first_name[:3] + last_name[:3]).lower()
    return f"https://media.formula1.com/image/upload/c_fill,w_720/q_auto/v1740000000/common/f1/2026/{team_slug}/{name_slug}01/2026{team_slug}{name_slug}01right.webp"

def generate_car_url(team_name: str) -> str:
    """Generate the URL for the 2026 team car image."""
    if "Red Bull" in team_name:
        return "https://www.formula1.com/en/teams/red-bull-racing" # Note: User provided team page, ideally we'd have a .webp but using as reference
    
    team_slug = team_name.lower().replace(" ", "").replace("racing", "").replace("f1team", "").replace("kick", "")
    if team_slug == "audi": team_slug = "audi"
    if team_slug == "cadillac": team_slug = "cadillac"
    return f"https://media.formula1.com/image/upload/c_lfill,w_512/q_auto/d_common:f1:2026:fallback:car:2026fallbackcarright.webp/v1740000000/common/f1/2026/{team_slug}/2026{team_slug}carright.webp"

class RaceSimulator:
    def __init__(self):
        self.lap = 1
        self.positions = []
        self.race_control_messages = []
        self._init_simulation()
    
    def _init_simulation(self):
        # Initialize basic positions
        self.positions = []
        for i, d in enumerate(DRIVERS_2026):
            first_name = d["FullName"].split(" ")[0]
            last_name = d["FullName"].split(" ")[-1]
            driver_info = {
                "position": i + 1,
                "tla": d["Tla"],
                "name": d["FullName"],
                "team": d["TeamName"],
                "gap": 0.0 if i == 0 else round(i * 1.5, 3), # 1.5s gap per car roughly
                "last_lap_time": "1:25.000",
                "photo_url": generate_driver_url(d["Tla"], first_name, last_name, d["TeamName"]),
                "car_url": generate_car_url(d["TeamName"]),
                "tyre": "M", # Medium by default
                "pit_stops": 0,
                "drs_enabled": False,
                "sector_times": ["28.1", "29.4", "27.5"]
            }
            self.positions.append(driver_info)
        
        self.race_control_messages.append({"lap": 1, "msg": "GREEN FLAG - Race Started"})

    def tick(self):
        """Simulate a tick in the race (roughly 1 lap progress or significant sector)"""
        self.lap += 1
        self.race_control_messages = [] # clear per lap for simplicity unless tracking history
        
        # Overtake (ex DRS) habilitado globalmente a partir de la vuelta 3
        global_drs = self.lap >= 3

        if self.lap == 3:
            self.race_control_messages.append({"lap": self.lap, "msg": "OVERTAKE ENABLED"})

        # Simple gap physics
        for i, driver in enumerate(self.positions):
            if i > 0:
                # Driver ahead
                ahead = self.positions[i-1]
                
                # Gap fluctuates slightly
                change = random.uniform(-0.3, 0.4)
                
                # Efecto Overtake
                if global_drs and driver["gap"] - ahead["gap"] < 1.0:
                    driver["drs_enabled"] = True
                    change -= 0.2  # Ganancia con Overtake
                else:
                    driver["drs_enabled"] = False
                
                driver["gap"] = max(0.0, round(driver["gap"] + change, 3))
                
                # Overtake condition
                if driver["gap"] < ahead["gap"]:
                    driver["gap"] = ahead["gap"] + 0.1 # Swap positions logically later
            
            # Generate fluctuating lap time around 1:24.xxx or 1:25.xxx
            seconds = random.randint(24, 26)
            ms = random.randint(0, 999)
            driver["last_lap_time"] = f"1:{seconds}.{ms:03d}"
            
            # Sector times (mocked summation)
            s1 = 28.0 + random.uniform(-0.2, 0.3)
            s2 = 29.0 + random.uniform(-0.2, 0.3)
            s3 = (seconds + ms/1000) - (s1 + s2)
            driver["sector_times"] = [f"{s1:.1f}", f"{s2:.1f}", f"{max(25.0, s3):.1f}"]

            # Random Pit Stop (exaggerated probability for testing narration)
            if self.lap > 5 and random.random() < 0.05 and driver["pit_stops"] == 0:
                driver["tyre"] = random.choice(["H", "S"])
                driver["pit_stops"] += 1
                stop_time = round(random.uniform(2.1, 3.5), 1)
                driver["gap"] += 22.0 # Pit lane loss
                self.race_control_messages.append({"lap": self.lap, "msg": f"{driver['tla']} IN PIT - {stop_time}s stop for {driver['tyre']} tyres"})
        
        # Re-sort positions based on gap
        self.positions.sort(key=lambda x: x["gap"])
        
        # Re-assign discrete positions and normalize leader gap to 0
        leader_gap = self.positions[0]["gap"]
        for i, driver in enumerate(self.positions):
            driver["position"] = i + 1
            driver["gap"] = round(driver["gap"] - leader_gap, 3)

    def get_state(self) -> Dict:
        return {
            "lap": self.lap,
            "positions": self.positions,
        }
