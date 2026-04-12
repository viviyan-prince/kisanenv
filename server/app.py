"""
KisanEnv — Real-World Agricultural Advisory OpenEnv Environment
An AI agent learns to advise farmers on crop management, pest control,
and weather-based decisions. Simulates the daily decisions a farming advisor makes.
"""

import os
import json
import random
import datetime
from typing import Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(
    title="KisanEnv",
    description="Real-world agricultural advisory environment for AI agents",
    version="1.0.0"
)

# ─── Environment State ────────────────────────────────────────────────────────

CROPS = ["rice", "wheat", "cotton", "sugarcane", "tomato", "onion", "potato"]
PESTS = ["aphid", "borer", "whitefly", "fungal_blight", "rust", "none"]
SEASONS = ["kharif", "rabi", "zaid"]
SOIL_TYPES = ["loamy", "clay", "sandy", "black_cotton", "red_laterite"]
WEATHER_CONDITIONS = ["sunny", "cloudy", "rainy", "drought", "flood_risk"]

VALID_ACTIONS = [
    "irrigate", "apply_fertilizer_nitrogen", "apply_fertilizer_phosphorus",
    "apply_pesticide_chemical", "apply_pesticide_organic", "harvest",
    "skip_day", "soil_test", "consult_weather", "plant_cover_crop",
    "apply_fungicide", "prune", "mulch"
]

# Crop requirements knowledge base
CROP_KNOWLEDGE = {
    "rice":      {"water_need": "high",   "pest_prone": ["fungal_blight", "borer"], "harvest_days": 120},
    "wheat":     {"water_need": "medium", "pest_prone": ["rust", "aphid"],           "harvest_days": 100},
    "cotton":    {"water_need": "medium", "pest_prone": ["borer", "whitefly"],       "harvest_days": 150},
    "sugarcane": {"water_need": "high",   "pest_prone": ["borer", "aphid"],          "harvest_days": 300},
    "tomato":    {"water_need": "medium", "pest_prone": ["whitefly", "fungal_blight"],"harvest_days": 75},
    "onion":     {"water_need": "low",    "pest_prone": ["fungal_blight", "aphid"],  "harvest_days": 90},
    "potato":    {"water_need": "medium", "pest_prone": ["fungal_blight", "borer"],  "harvest_days": 80},
}

class FarmState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.day = 0
        self.crop = random.choice(CROPS)
        self.soil_type = random.choice(SOIL_TYPES)
        self.season = random.choice(SEASONS)
        self.weather = random.choice(WEATHER_CONDITIONS)
        self.soil_moisture = random.uniform(0.3, 0.7)    # 0-1
        self.soil_nitrogen = random.uniform(0.3, 0.8)    # 0-1
        self.soil_phosphorus = random.uniform(0.3, 0.8)  # 0-1
        self.pest_level = random.choice(PESTS)
        self.crop_health = random.uniform(0.6, 1.0)       # 0-1
        self.days_to_harvest = CROP_KNOWLEDGE[self.crop]["harvest_days"]
        self.total_days = self.days_to_harvest + random.randint(0, 30)
        self.actions_taken = []
        self.warnings = []
        self.harvest_done = False
        self.yield_score = 0.0
        self._advance_day()
        return self.get_state()

    def _advance_day(self):
        """Simulate natural daily changes"""
        self.day += 1
        # Weather changes
        if random.random() < 0.2:
            self.weather = random.choice(WEATHER_CONDITIONS)
        # Moisture evaporation
        if self.weather in ["sunny", "drought"]:
            self.soil_moisture = max(0, self.soil_moisture - random.uniform(0.05, 0.12))
        elif self.weather == "rainy":
            self.soil_moisture = min(1.0, self.soil_moisture + random.uniform(0.1, 0.2))
        # Nutrient depletion
        self.soil_nitrogen = max(0, self.soil_nitrogen - 0.01)
        self.soil_phosphorus = max(0, self.soil_phosphorus - 0.005)
        # Pest spread
        if random.random() < 0.1 and self.pest_level == "none":
            self.pest_level = random.choice(CROP_KNOWLEDGE[self.crop]["pest_prone"])
        # Crop health degradation from stress
        if self.soil_moisture < 0.2 or self.soil_moisture > 0.9:
            self.crop_health = max(0, self.crop_health - 0.05)
        if self.pest_level != "none":
            self.crop_health = max(0, self.crop_health - 0.03)
        self.days_to_harvest = max(0, self.days_to_harvest - 1)
        # Generate warnings
        self.warnings = []
        if self.soil_moisture < 0.25:
            self.warnings.append("CRITICAL: Low soil moisture - irrigation needed urgently")
        if self.soil_nitrogen < 0.2:
            self.warnings.append("WARNING: Nitrogen deficiency detected")
        if self.pest_level != "none":
            self.warnings.append(f"ALERT: {self.pest_level} infestation detected")
        if self.weather == "flood_risk":
            self.warnings.append("WARNING: Flood risk - avoid irrigation")
        if self.days_to_harvest <= 5 and not self.harvest_done:
            self.warnings.append("INFO: Crop ready for harvest soon")

    def get_state(self) -> dict:
        return {
            "day": self.day,
            "crop": self.crop,
            "soil_type": self.soil_type,
            "season": self.season,
            "weather": self.weather,
            "soil_moisture": round(self.soil_moisture, 3),
            "soil_nitrogen": round(self.soil_nitrogen, 3),
            "soil_phosphorus": round(self.soil_phosphorus, 3),
            "pest_level": self.pest_level,
            "crop_health": round(self.crop_health, 3),
            "days_to_harvest": self.days_to_harvest,
            "warnings": self.warnings,
            "harvest_done": self.harvest_done,
            "valid_actions": VALID_ACTIONS,
        }

    def step(self, action: str) -> dict:
        if action not in VALID_ACTIONS:
            return {
                "observation": self.get_state(),
                "reward": -0.1,
                "done": False,
                "info": {"error": f"Invalid action: {action}", "valid_actions": VALID_ACTIONS}
            }

        reward = 0.0
        info = {"action": action, "day": self.day}

        # ── Action effects ────────────────────────────────────────
        if action == "irrigate":
            if self.weather == "flood_risk":
                reward = -0.2
                info["result"] = "Bad decision: flood risk, irrigation caused waterlogging"
                self.crop_health = max(0, self.crop_health - 0.1)
            elif self.soil_moisture > 0.8:
                reward = -0.05
                info["result"] = "Over-irrigation: moisture already high"
            else:
                added = random.uniform(0.15, 0.25)
                self.soil_moisture = min(1.0, self.soil_moisture + added)
                reward = 0.15 if self.soil_moisture < 0.4 else 0.05
                info["result"] = f"Irrigated. Moisture: {self.soil_moisture:.2f}"
                self.crop_health = min(1.0, self.crop_health + 0.02)

        elif action == "apply_fertilizer_nitrogen":
            if self.soil_nitrogen < 0.4:
                self.soil_nitrogen = min(1.0, self.soil_nitrogen + 0.25)
                reward = 0.2
                info["result"] = "Nitrogen applied. Soil health improved."
                self.crop_health = min(1.0, self.crop_health + 0.05)
            else:
                reward = -0.05
                info["result"] = "Unnecessary fertilizer. Nitrogen already adequate."

        elif action == "apply_fertilizer_phosphorus":
            if self.soil_phosphorus < 0.4:
                self.soil_phosphorus = min(1.0, self.soil_phosphorus + 0.2)
                reward = 0.15
                info["result"] = "Phosphorus applied."
            else:
                reward = -0.03
                info["result"] = "Phosphorus already adequate."

        elif action == "apply_pesticide_chemical":
            if self.pest_level != "none":
                self.pest_level = "none"
                reward = 0.25
                info["result"] = "Chemical pesticide applied. Pest eliminated."
                self.crop_health = min(1.0, self.crop_health + 0.1)
            else:
                reward = -0.1
                info["result"] = "No pest present. Unnecessary chemical use."

        elif action == "apply_pesticide_organic":
            if self.pest_level != "none":
                self.pest_level = "none" if random.random() > 0.3 else self.pest_level
                reward = 0.2 if self.pest_level == "none" else 0.05
                info["result"] = "Organic pesticide applied."
            else:
                reward = -0.05
                info["result"] = "No pest. Organic spray wasted."

        elif action == "apply_fungicide":
            if self.pest_level in ["fungal_blight", "rust"]:
                self.pest_level = "none"
                reward = 0.3
                info["result"] = "Fungicide highly effective against fungal pest."
                self.crop_health = min(1.0, self.crop_health + 0.12)
            elif self.pest_level != "none":
                reward = 0.0
                info["result"] = "Fungicide has no effect on this pest type."
            else:
                reward = -0.05
                info["result"] = "No fungal disease present."

        elif action == "harvest":
            if self.days_to_harvest <= 10:
                self.yield_score = self.crop_health * (0.8 + 0.2 * (self.soil_moisture))
                reward = self.yield_score * 1.0
                self.harvest_done = True
                info["result"] = f"Harvest successful! Yield score: {self.yield_score:.2f}"
                info["yield_score"] = self.yield_score
            elif self.days_to_harvest > 10:
                reward = -0.3
                self.crop_health = max(0, self.crop_health - 0.2)
                info["result"] = f"Too early to harvest! {self.days_to_harvest} days remaining. Crop damaged."

        elif action == "skip_day":
            reward = -0.02
            info["result"] = "Day skipped. No action taken."

        elif action == "soil_test":
            reward = 0.05
            info["result"] = (f"Soil test: N={self.soil_nitrogen:.2f}, "
                              f"P={self.soil_phosphorus:.2f}, "
                              f"Moisture={self.soil_moisture:.2f}")
            info["soil_report"] = {
                "nitrogen": self.soil_nitrogen,
                "phosphorus": self.soil_phosphorus,
                "moisture": self.soil_moisture,
                "soil_type": self.soil_type,
            }

        elif action == "consult_weather":
            reward = 0.03
            info["result"] = f"Weather forecast: {self.weather}. Season: {self.season}."
            info["forecast"] = {"weather": self.weather, "season": self.season}

        elif action == "plant_cover_crop":
            self.soil_nitrogen = min(1.0, self.soil_nitrogen + 0.05)
            reward = 0.08
            info["result"] = "Cover crop planted. Long-term soil improvement."

        elif action == "prune":
            self.crop_health = min(1.0, self.crop_health + 0.04)
            reward = 0.06
            info["result"] = "Pruning done. Improved airflow and crop health."

        elif action == "mulch":
            self.soil_moisture = min(1.0, self.soil_moisture + 0.05)
            reward = 0.07
            info["result"] = "Mulch applied. Moisture retention improved."

        # ── Advance the day ───────────────────────────────────────
        self._advance_day()
        self.actions_taken.append(action)

        done = self.harvest_done or self.day >= self.total_days or self.crop_health <= 0

        # Terminal penalties/bonuses
        if done and not self.harvest_done:
            if self.crop_health <= 0:
                reward += -0.5
                info["terminal"] = "Crop died. Total failure."
            else:
                reward += -0.3
                info["terminal"] = "Season ended without harvest."

        obs = self.get_state()
        obs["actions_taken_count"] = len(self.actions_taken)
        return {
            "observation": obs,
            "reward": round(reward, 4),
            "done": done,
            "info": info
        }


# ─── Global State (one session per HF Space instance) ────────────────────────
farm = FarmState()


# ─── OpenEnv API Endpoints ────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "KisanEnv",
        "description": "Real-world agricultural advisory OpenEnv environment",
        "version": "1.0.0",
        "endpoints": {
            "reset": "POST /reset",
            "step": "POST /step",
            "state": "GET /state",
            "validate": "GET /openenv/validate",
        }
    }

@app.post("/reset")
def reset():
    """Reset the environment to initial state"""
    state = farm.reset()
    return {
        "observation": state,
        "info": {
            "message": "Environment reset successfully",
            "crop": farm.crop,
            "season": farm.season,
            "total_days": farm.total_days,
        }
    }

class StepRequest(BaseModel):
    action: str

@app.post("/step")
def step(req: StepRequest):
    """Take an action in the environment"""
    result = farm.step(req.action)
    return result

@app.get("/state")
def state():
    """Get current environment state"""
    s = farm.get_state()
    s["actions_taken_count"] = len(farm.actions_taken)
    return {"observation": s}

@app.get("/openenv/validate")
def validate():
    """OpenEnv spec validation endpoint"""
    return {
        "name": "KisanEnv",
        "version": "1.0.0",
        "openenv_compliant": True,
        "observation_space": {
            "day": "int",
            "crop": "str",
            "soil_type": "str",
            "season": "str",
            "weather": "str",
            "soil_moisture": "float [0,1]",
            "soil_nitrogen": "float [0,1]",
            "soil_phosphorus": "float [0,1]",
            "pest_level": "str",
            "crop_health": "float [0,1]",
            "days_to_harvest": "int",
            "warnings": "list[str]",
            "harvest_done": "bool",
            "valid_actions": "list[str]"
        },
        "action_space": VALID_ACTIONS,
        "reward_range": [-1.0, 1.0],
        "tasks": [
            {
                "id": "task_easy",
                "name": "Irrigation Management",
                "difficulty": "easy",
                "description": "Keep soil moisture above 0.4 for 20 days",
                "reward_range": [0.0, 1.0]
            },
            {
                "id": "task_medium",
                "name": "Pest & Nutrient Control",
                "difficulty": "medium",
                "description": "Maintain crop health above 0.7 while managing pests and nutrients",
                "reward_range": [0.0, 1.0]
            },
            {
                "id": "task_hard",
                "name": "Full Season Yield Optimization",
                "difficulty": "hard",
                "description": "Complete a full growing season with maximum yield score",
                "reward_range": [0.0, 1.0]
            }
        ],
        "endpoints": {
            "reset": {"method": "POST", "path": "/reset"},
            "step": {"method": "POST", "path": "/step"},
            "state": {"method": "GET", "path": "/state"},
        }
    }


# ─── Grader Endpoints ─────────────────────────────────────────────────────────

@app.get("/grade/easy")
def grade_easy():
    """Easy grader: Was soil moisture maintained?"""
    moisture = farm.soil_moisture
    score = min(1.0, moisture / 0.6)
    return {
        "task": "irrigation_management",
        "difficulty": "easy",
        "score": round(score, 4),
        "criteria": "Soil moisture level",
        "current_moisture": moisture,
        "pass_threshold": 0.4
    }

@app.get("/grade/medium")
def grade_medium():
    """Medium grader: Crop health and pest management"""
    health_score = farm.crop_health
    pest_penalty = 0.3 if farm.pest_level != "none" else 0.0
    nutrient_score = (farm.soil_nitrogen + farm.soil_phosphorus) / 2
    score = (health_score * 0.5 + nutrient_score * 0.3 - pest_penalty + 0.2)
    score = max(0.0, min(1.0, score))
    return {
        "task": "pest_nutrient_control",
        "difficulty": "medium",
        "score": round(score, 4),
        "breakdown": {
            "crop_health": health_score,
            "nutrient_level": nutrient_score,
            "pest_penalty": pest_penalty
        }
    }

@app.get("/grade/hard")
def grade_hard():
    """Hard grader: Full season yield optimization"""
    if farm.harvest_done:
        score = farm.yield_score
    else:
        # Partial credit
        days_progress = min(1.0, farm.day / max(1, farm.total_days))
        score = farm.crop_health * 0.3 * days_progress
    return {
        "task": "full_season_yield",
        "difficulty": "hard",
        "score": round(max(0.0, min(1.0, score)), 4),
        "harvest_done": farm.harvest_done,
        "yield_score": farm.yield_score,
        "crop_health": farm.crop_health
    }


def main():
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
