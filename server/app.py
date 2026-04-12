"""
KisanEnv - Agricultural Advisory OpenEnv Environment
"""
import os
import random
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="KisanEnv", version="1.0.0")

# ── Constants ──────────────────────────────────────────────────────────────────
CROPS   = ["rice", "wheat", "cotton", "tomato", "onion", "potato"]
PESTS   = ["aphid", "borer", "fungal_blight", "rust", "none"]
WEATHER = ["sunny", "cloudy", "rainy", "drought", "flood_risk"]
ACTIONS = [
    "irrigate", "apply_fertilizer_nitrogen", "apply_fertilizer_phosphorus",
    "apply_pesticide_chemical", "apply_pesticide_organic", "apply_fungicide",
    "harvest", "skip_day", "soil_test", "consult_weather",
    "plant_cover_crop", "prune", "mulch"
]
HARVEST_DAYS = {"rice": 120, "wheat": 100, "cotton": 150,
                "tomato": 75, "onion": 90, "potato": 80}

# ── In-memory state (module level, always initialised) ────────────────────────
state = {}

def _new_state():
    crop = random.choice(CROPS)
    return {
        "day":              1,
        "crop":             crop,
        "soil_type":        random.choice(["loamy","clay","sandy","black_cotton"]),
        "season":           random.choice(["kharif","rabi","zaid"]),
        "weather":          random.choice(WEATHER),
        "soil_moisture":    round(random.uniform(0.35, 0.70), 3),
        "soil_nitrogen":    round(random.uniform(0.35, 0.75), 3),
        "soil_phosphorus":  round(random.uniform(0.35, 0.75), 3),
        "pest_level":       "none",
        "crop_health":      round(random.uniform(0.70, 1.00), 3),
        "days_to_harvest":  HARVEST_DAYS[crop],
        "total_days":       HARVEST_DAYS[crop] + 20,
        "harvest_done":     False,
        "yield_score":      0.0,
        "warnings":         [],
        "valid_actions":    ACTIONS,
    }

def _obs(s):
    """Return observation dict (everything except internal fields)."""
    return {k: v for k, v in s.items() if k != "total_days"}

def _advance(s):
    s["day"] += 1
    if random.random() < 0.2:
        s["weather"] = random.choice(WEATHER)
    if s["weather"] in ("sunny", "drought"):
        s["soil_moisture"] = max(0.0, s["soil_moisture"] - round(random.uniform(0.04, 0.10), 3))
    elif s["weather"] == "rainy":
        s["soil_moisture"] = min(1.0, s["soil_moisture"] + round(random.uniform(0.08, 0.18), 3))
    s["soil_nitrogen"]   = max(0.0, s["soil_nitrogen"]   - 0.008)
    s["soil_phosphorus"] = max(0.0, s["soil_phosphorus"] - 0.004)
    if random.random() < 0.08 and s["pest_level"] == "none":
        s["pest_level"] = random.choice(["aphid","borer","fungal_blight","rust"])
    if s["soil_moisture"] < 0.2 or s["pest_level"] != "none":
        s["crop_health"] = max(0.0, s["crop_health"] - 0.025)
    s["days_to_harvest"] = max(0, s["days_to_harvest"] - 1)
    # warnings
    w = []
    if s["soil_moisture"]   < 0.25: w.append("CRITICAL: Low moisture")
    if s["soil_nitrogen"]   < 0.20: w.append("WARNING: Nitrogen low")
    if s["pest_level"] != "none":   w.append(f"ALERT: {s['pest_level']} detected")
    if s["days_to_harvest"] <= 5 and not s["harvest_done"]:
        w.append("INFO: Ready to harvest")
    s["warnings"] = w

# Initialise on startup
state.update(_new_state())

# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"name": "KisanEnv", "version": "1.0.0", "status": "running"}

@app.post("/reset")
def reset():
    state.clear()
    state.update(_new_state())
    return {"observation": _obs(state), "info": {"crop": state["crop"], "season": state["season"]}}

class StepRequest(BaseModel):
    action: str

@app.post("/step")
def step(req: StepRequest):
    action  = req.action
    reward  = 0.0
    info    = {"action": action}

    if action not in ACTIONS:
        return {"observation": _obs(state), "reward": -0.1, "done": False,
                "info": {"error": f"invalid action: {action}"}}

    m = state["soil_moisture"]
    n = state["soil_nitrogen"]
    p = state["soil_phosphorus"]
    pest = state["pest_level"]
    w = state["weather"]

    if action == "irrigate":
        if w == "flood_risk":
            reward = -0.2; state["crop_health"] = max(0, state["crop_health"]-0.08)
            info["result"] = "Bad: flood risk"
        elif m > 0.8:
            reward = -0.05; info["result"] = "Over-irrigation"
        else:
            state["soil_moisture"] = min(1.0, m + random.uniform(0.12, 0.22))
            reward = 0.15 if m < 0.35 else 0.05
            info["result"] = "Irrigated"

    elif action == "apply_fertilizer_nitrogen":
        if n < 0.4:
            state["soil_nitrogen"] = min(1.0, n + 0.22)
            state["crop_health"]   = min(1.0, state["crop_health"] + 0.04)
            reward = 0.18; info["result"] = "Nitrogen applied"
        else:
            reward = -0.04; info["result"] = "Nitrogen not needed"

    elif action == "apply_fertilizer_phosphorus":
        if p < 0.4:
            state["soil_phosphorus"] = min(1.0, p + 0.18)
            reward = 0.12; info["result"] = "Phosphorus applied"
        else:
            reward = -0.03; info["result"] = "Phosphorus not needed"

    elif action == "apply_pesticide_chemical":
        if pest != "none":
            state["pest_level"] = "none"
            state["crop_health"] = min(1.0, state["crop_health"] + 0.10)
            reward = 0.25; info["result"] = "Pest eliminated"
        else:
            reward = -0.08; info["result"] = "No pest present"

    elif action == "apply_pesticide_organic":
        if pest != "none":
            if random.random() > 0.3:
                state["pest_level"] = "none"
                reward = 0.18; info["result"] = "Pest eliminated (organic)"
            else:
                reward = 0.04; info["result"] = "Partial effect"
        else:
            reward = -0.04; info["result"] = "No pest present"

    elif action == "apply_fungicide":
        if pest in ("fungal_blight", "rust"):
            state["pest_level"] = "none"
            state["crop_health"] = min(1.0, state["crop_health"] + 0.12)
            reward = 0.28; info["result"] = "Fungal pest eliminated"
        elif pest != "none":
            reward = 0.0;  info["result"] = "Wrong pesticide type"
        else:
            reward = -0.04; info["result"] = "No pest present"

    elif action == "harvest":
        if state["days_to_harvest"] <= 10:
            ys = round(state["crop_health"] * (0.8 + 0.2 * state["soil_moisture"]), 4)
            state["yield_score"]  = ys
            state["harvest_done"] = True
            reward = ys; info["result"] = f"Harvested! yield={ys}"
        else:
            state["crop_health"] = max(0, state["crop_health"] - 0.18)
            reward = -0.28; info["result"] = "Too early to harvest"

    elif action == "skip_day":
        reward = -0.02; info["result"] = "Skipped"

    elif action == "soil_test":
        reward = 0.04
        info["result"] = f"N={state['soil_nitrogen']:.2f} P={state['soil_phosphorus']:.2f} M={state['soil_moisture']:.2f}"

    elif action == "consult_weather":
        reward = 0.02; info["result"] = f"Weather: {state['weather']}"

    elif action == "plant_cover_crop":
        state["soil_nitrogen"] = min(1.0, state["soil_nitrogen"] + 0.04)
        reward = 0.06; info["result"] = "Cover crop planted"

    elif action == "prune":
        state["crop_health"] = min(1.0, state["crop_health"] + 0.04)
        reward = 0.05; info["result"] = "Pruned"

    elif action == "mulch":
        state["soil_moisture"] = min(1.0, state["soil_moisture"] + 0.04)
        reward = 0.05; info["result"] = "Mulched"

    _advance(state)
    done = state["harvest_done"] or state["day"] >= state["total_days"] or state["crop_health"] <= 0
    if done and not state["harvest_done"]:
        reward += (-0.4 if state["crop_health"] <= 0 else -0.2)

    return {"observation": _obs(state), "reward": round(reward, 4), "done": done, "info": info}

@app.get("/state")
def get_state():
    return {"observation": _obs(state)}

@app.get("/openenv/validate")
def validate():
    return {
        "name": "KisanEnv", "version": "1.0.0", "openenv_compliant": True,
        "observation_space": {
            "day": "int", "crop": "str", "soil_type": "str", "season": "str",
            "weather": "str", "soil_moisture": "float[0,1]",
            "soil_nitrogen": "float[0,1]", "soil_phosphorus": "float[0,1]",
            "pest_level": "str", "crop_health": "float[0,1]",
            "days_to_harvest": "int", "warnings": "list[str]",
            "harvest_done": "bool", "valid_actions": "list[str]"
        },
        "action_space": ACTIONS,
        "reward_range": [-1.0, 1.0],
        "tasks": [
            {"id": "task_easy",   "name": "Irrigation Management",      "difficulty": "easy",   "score_range": [0.0, 1.0]},
            {"id": "task_medium", "name": "Pest and Nutrient Control",   "difficulty": "medium", "score_range": [0.0, 1.0]},
            {"id": "task_hard",   "name": "Full Season Yield",           "difficulty": "hard",   "score_range": [0.0, 1.0]},
        ]
    }

@app.get("/grade/easy")
def grade_easy():
    score = min(1.0, state["soil_moisture"] / 0.55)
    return {"task": "irrigation_management", "difficulty": "easy", "score": round(score, 4)}

@app.get("/grade/medium")
def grade_medium():
    pest_penalty = 0.25 if state["pest_level"] != "none" else 0.0
    score = max(0.0, min(1.0,
        state["crop_health"] * 0.5 +
        (state["soil_nitrogen"] + state["soil_phosphorus"]) / 2 * 0.3 +
        0.2 - pest_penalty
    ))
    return {"task": "pest_nutrient_control", "difficulty": "medium", "score": round(score, 4)}

@app.get("/grade/hard")
def grade_hard():
    if state["harvest_done"]:
        score = state["yield_score"]
    else:
        score = state["crop_health"] * 0.3 * min(1.0, state["day"] / max(1, state["total_days"]))
    return {"task": "full_season_yield", "difficulty": "hard",
            "score": round(max(0.0, min(1.0, score)), 4),
            "harvest_done": state["harvest_done"]}

def main():
    uvicorn.run(app, host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()
