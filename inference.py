"""
KisanEnv — Baseline Inference Script
START/STEP/END format. Uses OpenAI client via env vars.
"""

import os
import json
import time
import requests
from openai import OpenAI

# ─── REQUIRED env vars ────────────────────────────────────────────────────────
API_BASE_URL     = os.getenv("API_BASE_URL", "<your-active-space-url>")
MODEL_NAME       = os.getenv("MODEL_NAME",   "<your-active-model-name>")
HF_TOKEN         = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# ─── Wait for Space to wake up ────────────────────────────────────────────────
def wait_for_space():
    for i in range(20):          # up to 120 seconds
        try:
            r = requests.get(f"{API_BASE_URL}/", timeout=10)
            if r.status_code == 200:
                print(json.dumps({"type": "WARN", "message": "Space is ready"}))
                return
        except Exception:
            pass
        print(json.dumps({"type": "WARN", "message": f"Waiting for space... attempt {i+1}/20"}))
        time.sleep(6)

# ─── Env helpers ──────────────────────────────────────────────────────────────
def env_reset():
    for i in range(10):          # up to 100 seconds of retries
        try:
            r = requests.post(f"{API_BASE_URL}/reset", timeout=20)
            if r.status_code == 200:
                return r.json()
            print(json.dumps({"type": "WARN", "message": f"Reset {r.status_code}, retry {i+1}"}))
        except Exception as e:
            print(json.dumps({"type": "WARN", "message": f"Reset error: {e}, retry {i+1}"}))
        time.sleep(10)
    raise RuntimeError("Space /reset never responded after 10 attempts")

def env_step(action):
    for i in range(5):
        try:
            r = requests.post(f"{API_BASE_URL}/step", json={"action": action}, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(json.dumps({"type": "WARN", "message": f"Step error: {e}"}))
        time.sleep(3)
    return {"observation": {}, "reward": 0.0, "done": True, "info": {}}

# ─── Rule-based agent (fallback) ──────────────────────────────────────────────
def decide(obs):
    try:
        client = OpenAI(
            base_url=API_BASE_URL,
            api_key=HF_TOKEN if HF_TOKEN else "no-key",
        )
        r = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Pick one action from valid_actions. Reply with just the action name."},
                {"role": "user",   "content": json.dumps(obs)}
            ],
            max_tokens=15, temperature=0.1,
        )
        action = r.choices[0].message.content.strip().lower().replace('"','').replace("'","")
        if action in obs.get("valid_actions", []):
            return action
    except Exception:
        pass
    # rule-based fallback
    if obs.get("pest_level","none") != "none":
        return "apply_fungicide" if obs["pest_level"] in ("fungal_blight","rust") else "apply_pesticide_organic"
    if obs.get("soil_moisture", 0.5) < 0.3 and obs.get("weather") != "flood_risk":
        return "irrigate"
    if obs.get("soil_nitrogen", 0.5) < 0.3:
        return "apply_fertilizer_nitrogen"
    if obs.get("soil_phosphorus", 0.5) < 0.3:
        return "apply_fertilizer_phosphorus"
    if obs.get("days_to_harvest", 999) <= 5:
        return "harvest"
    return "skip_day"

# ─── Main ─────────────────────────────────────────────────────────────────────
def run_inference():
    wait_for_space()

    print(json.dumps({"type": "START", "model": MODEL_NAME, "environment": "KisanEnv"}))

    obs = env_reset().get("observation", {})
    total_reward = 0.0

    for step in range(50):
        action = decide(obs)
        result = env_step(action)
        obs    = result.get("observation", {})
        reward = result.get("reward", 0.0)
        done   = result.get("done", False)
        total_reward += reward

        print(json.dumps({
            "type": "STEP", "step": step + 1, "action": action,
            "reward": reward, "done": done,
            "crop_health":     obs.get("crop_health"),
            "soil_moisture":   obs.get("soil_moisture"),
            "pest_level":      obs.get("pest_level"),
            "days_to_harvest": obs.get("days_to_harvest"),
        }))

        if done:
            break

    easy = medium = hard = 0.0
    try:
        easy   = requests.get(f"{API_BASE_URL}/grade/easy",   timeout=10).json().get("score", 0)
        medium = requests.get(f"{API_BASE_URL}/grade/medium", timeout=10).json().get("score", 0)
        hard   = requests.get(f"{API_BASE_URL}/grade/hard",   timeout=10).json().get("score", 0)
    except Exception:
        pass

    print(json.dumps({
        "type": "END", "total_reward": round(total_reward, 4),
        "scores": {"easy": easy, "medium": medium, "hard": hard}
    }))

if __name__ == "__main__":
    run_inference()
