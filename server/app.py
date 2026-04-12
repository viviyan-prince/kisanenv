"""
KisanEnv - Agricultural Advisory OpenEnv Environment
"""
import random
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="KisanEnv", version="1.0.0")

CROPS   = ["rice", "wheat", "cotton", "tomato", "onion", "potato"]
WEATHER = ["sunny", "cloudy", "rainy", "drought", "flood_risk"]
ACTIONS = [
    "irrigate", "apply_fertilizer_nitrogen", "apply_fertilizer_phosphorus",
    "apply_pesticide_chemical", "apply_pesticide_organic", "apply_fungicide",
    "harvest", "skip_day", "soil_test", "consult_weather",
    "plant_cover_crop", "prune", "mulch"
]
HARVEST_DAYS = {"rice":120,"wheat":100,"cotton":150,"tomato":75,"onion":90,"potato":80}

def new_state():
    crop = random.choice(CROPS)
    hd   = HARVEST_DAYS[crop]
    return {
        "day":0, "crop":crop,
        "soil_type":   random.choice(["loamy","clay","sandy","black_cotton"]),
        "season":      random.choice(["kharif","rabi","zaid"]),
        "weather":     random.choice(WEATHER),
        "soil_moisture":   round(random.uniform(0.40,0.70),3),
        "soil_nitrogen":   round(random.uniform(0.40,0.75),3),
        "soil_phosphorus": round(random.uniform(0.40,0.75),3),
        "pest_level":  "none",
        "crop_health": round(random.uniform(0.75,1.00),3),
        "days_to_harvest": hd,
        "_total_days": hd + 20,
        "harvest_done":False,
        "yield_score": 0.0,
        "warnings":    [],
        "valid_actions": ACTIONS,
    }

S = new_state()   # global state

def obs():
    return {k:v for k,v in S.items() if not k.startswith("_")}

def advance():
    S["day"] += 1
    if random.random() < 0.2:
        S["weather"] = random.choice(WEATHER)
    if S["weather"] in ("sunny","drought"):
        S["soil_moisture"] = max(0.0, S["soil_moisture"] - round(random.uniform(0.04,0.10),3))
    elif S["weather"] == "rainy":
        S["soil_moisture"] = min(1.0, S["soil_moisture"] + round(random.uniform(0.08,0.18),3))
    S["soil_nitrogen"]   = max(0.0, round(S["soil_nitrogen"]   - 0.008, 4))
    S["soil_phosphorus"] = max(0.0, round(S["soil_phosphorus"] - 0.004, 4))
    if random.random() < 0.08 and S["pest_level"] == "none":
        S["pest_level"] = random.choice(["aphid","borer","fungal_blight","rust"])
    if S["soil_moisture"] < 0.2 or S["pest_level"] != "none":
        S["crop_health"] = max(0.0, round(S["crop_health"] - 0.025, 4))
    S["days_to_harvest"] = max(0, S["days_to_harvest"] - 1)
    w = []
    if S["soil_moisture"]   < 0.25: w.append("CRITICAL: Low moisture")
    if S["soil_nitrogen"]   < 0.20: w.append("WARNING: Nitrogen low")
    if S["pest_level"] != "none":   w.append(f"ALERT: {S['pest_level']} detected")
    if S["days_to_harvest"] <= 5 and not S["harvest_done"]:
        w.append("INFO: Ready to harvest")
    S["warnings"] = w

@app.get("/")
def root():
    return {"name":"KisanEnv","version":"1.0.0","status":"running"}

@app.post("/reset")
def reset():
    global S
    S = new_state()
    return {"observation": obs(), "info": {"crop": S["crop"], "season": S["season"]}}

class StepReq(BaseModel):
    action: str

@app.post("/step")
def step(req: StepReq):
    global S
    action = req.action
    reward = 0.0
    info   = {"action": action}

    if action not in ACTIONS:
        return {"observation":obs(),"reward":-0.1,"done":False,
                "info":{"error":f"invalid: {action}"}}

    m, n, p = S["soil_moisture"], S["soil_nitrogen"], S["soil_phosphorus"]
    pest, w = S["pest_level"], S["weather"]

    if action == "irrigate":
        if w == "flood_risk":
            reward=-0.2; S["crop_health"]=max(0,S["crop_health"]-0.08)
            info["result"]="Bad: flood risk"
        elif m > 0.80:
            reward=-0.05; info["result"]="Over-irrigation"
        else:
            S["soil_moisture"]=min(1.0,m+round(random.uniform(0.12,0.22),3))
            reward=0.15 if m<0.35 else 0.05; info["result"]="Irrigated"

    elif action == "apply_fertilizer_nitrogen":
        if n < 0.40:
            S["soil_nitrogen"]=min(1.0,n+0.22)
            S["crop_health"]=min(1.0,S["crop_health"]+0.04)
            reward=0.18; info["result"]="Nitrogen applied"
        else:
            reward=-0.04; info["result"]="Not needed"

    elif action == "apply_fertilizer_phosphorus":
        if p < 0.40:
            S["soil_phosphorus"]=min(1.0,p+0.18)
            reward=0.12; info["result"]="Phosphorus applied"
        else:
            reward=-0.03; info["result"]="Not needed"

    elif action == "apply_pesticide_chemical":
        if pest != "none":
            S["pest_level"]="none"; S["crop_health"]=min(1.0,S["crop_health"]+0.10)
            reward=0.25; info["result"]="Pest eliminated"
        else:
            reward=-0.08; info["result"]="No pest"

    elif action == "apply_pesticide_organic":
        if pest != "none":
            if random.random()>0.3:
                S["pest_level"]="none"; reward=0.18; info["result"]="Pest eliminated"
            else:
                reward=0.04; info["result"]="Partial effect"
        else:
            reward=-0.04; info["result"]="No pest"

    elif action == "apply_fungicide":
        if pest in ("fungal_blight","rust"):
            S["pest_level"]="none"; S["crop_health"]=min(1.0,S["crop_health"]+0.12)
            reward=0.28; info["result"]="Fungal pest eliminated"
        elif pest != "none":
            reward=0.0; info["result"]="Wrong type"
        else:
            reward=-0.04; info["result"]="No pest"

    elif action == "harvest":
        if S["days_to_harvest"] <= 10:
            ys=round(S["crop_health"]*(0.8+0.2*S["soil_moisture"]),4)
            S["yield_score"]=ys; S["harvest_done"]=True
            reward=ys; info["result"]=f"Harvested yield={ys}"
        else:
            S["crop_health"]=max(0,S["crop_health"]-0.18)
            reward=-0.28; info["result"]="Too early"

    elif action == "skip_day":
        reward=-0.02; info["result"]="Skipped"

    elif action == "soil_test":
        reward=0.04
        info["result"]=f"N={S['soil_nitrogen']:.2f} P={S['soil_phosphorus']:.2f} M={S['soil_moisture']:.2f}"

    elif action == "consult_weather":
        reward=0.02; info["result"]=f"Weather:{S['weather']}"

    elif action == "plant_cover_crop":
        S["soil_nitrogen"]=min(1.0,S["soil_nitrogen"]+0.04)
        reward=0.06; info["result"]="Cover crop planted"

    elif action == "prune":
        S["crop_health"]=min(1.0,S["crop_health"]+0.04)
        reward=0.05; info["result"]="Pruned"

    elif action == "mulch":
        S["soil_moisture"]=min(1.0,S["soil_moisture"]+0.04)
        reward=0.05; info["result"]="Mulched"

    advance()
    done = S["harvest_done"] or S["day"]>=S["_total_days"] or S["crop_health"]<=0
    if done and not S["harvest_done"]:
        reward += -0.4 if S["crop_health"]<=0 else -0.2

    return {"observation":obs(),"reward":round(reward,4),"done":done,"info":info}

@app.get("/state")
def get_state():
    return {"observation": obs()}

@app.get("/openenv/validate")
def validate():
    return {
        "name":"KisanEnv","version":"1.0.0","openenv_compliant":True,
        "observation_space":{
            "day":"int","crop":"str","soil_type":"str","season":"str",
            "weather":"str","soil_moisture":"float[0,1]",
            "soil_nitrogen":"float[0,1]","soil_phosphorus":"float[0,1]",
            "pest_level":"str","crop_health":"float[0,1]",
            "days_to_harvest":"int","warnings":"list[str]",
            "harvest_done":"bool","valid_actions":"list[str]"
        },
        "action_space": ACTIONS,
        "reward_range": [-1.0, 1.0],
        "tasks":[
            {"id":"task_easy",  "name":"Irrigation Management",   "difficulty":"easy",  "score_range":[0.0,1.0]},
            {"id":"task_medium","name":"Pest and Nutrient Control","difficulty":"medium","score_range":[0.0,1.0]},
            {"id":"task_hard",  "name":"Full Season Yield",        "difficulty":"hard",  "score_range":[0.0,1.0]},
        ]
    }

@app.get("/grade/easy")
def grade_easy():
    return {"task":"irrigation_management","difficulty":"easy",
            "score":round(min(1.0,S["soil_moisture"]/0.55),4)}

@app.get("/grade/medium")
def grade_medium():
    pen = 0.25 if S["pest_level"]!="none" else 0.0
    sc  = max(0.0,min(1.0,S["crop_health"]*0.5+(S["soil_nitrogen"]+S["soil_phosphorus"])/2*0.3+0.2-pen))
    return {"task":"pest_nutrient_control","difficulty":"medium","score":round(sc,4)}

@app.get("/grade/hard")
def grade_hard():
    sc = S["yield_score"] if S["harvest_done"] else S["crop_health"]*0.3*min(1.0,S["day"]/max(1,S["_total_days"]))
    return {"task":"full_season_yield","difficulty":"hard",
            "score":round(max(0.0,min(1.0,sc)),4),"harvest_done":S["harvest_done"]}

def main():
    uvicorn.run(app, host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()
