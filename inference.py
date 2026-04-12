"""
KisanEnv — Baseline Inference Script
Follows the EXACT OpenEnv hackathon format with START/STEP/END logs.
Uses the OpenAI client (configured via environment variables) as the LLM backbone.
"""

import os
import json
import time
import requests
from openai import OpenAI

# ─── Environment Configuration (REQUIRED) ─────────────────────────────────────
API_BASE_URL     = os.getenv("API_BASE_URL", "<your-active-space-url>")
MODEL_NAME       = os.getenv("MODEL_NAME",   "<your-active-model-name>")
HF_TOKEN         = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# ─── Helper: wait for Space to be ready ───────────────────────────────────────
def wait_for_space(retries=10, delay=6):
    """Ping root until Space responds, with retries."""
    for i in range(retries):
        try:
            r = requests.get(f"{API_BASE_URL}/", timeout=15)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        print(json.dumps({"type": "WARN", "message": f"Space not ready, retry {i+1}/{retries}..."}))
        time.sleep(delay)
    return False

# ─── Helper: Call the environment ─────────────────────────────────────────────
def env_reset(retries=5, delay=5):
    for attempt in range(retries):
        try:
            resp = requests.post(f"{API_BASE_URL}/reset", timeout=30)
            if resp.status_code == 200:
                return resp.json()
            print(json.dumps({"type": "WARN", "message": f"Reset returned {resp.status_code}, retry {attempt+1}"}))
        except Exception as e:
            print(json.dumps({"type": "WARN", "message": f"Reset error: {str(e)}, retry {attempt+1}"}))
        time.sleep(delay)
    raise RuntimeError(f"Reset failed after {retries} attempts")

def env_step(action: str, retries=3, delay=3):
    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{API_BASE_URL}/step",
                json={"action": action},
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json()
            print(json.dumps({"type": "WARN", "message": f"Step returned {resp.status_code}"}))
        except Exception as e:
            print(json.dumps({"type": "WARN", "message": f"Step error: {str(e)}, retry {attempt+1}"}))
        time.sleep(delay)
    # Return a safe fallback so execution continues
    return {"observation": {}, "reward": 0.0, "done": True, "info": {"error": "step failed"}}

# ─── Rule-based fallback ──────────────────────────────────────────────────────
def rule_based_fallback(obs: dict) -> str:
    if obs.get("pest_level", "none") != "none":
        pest = obs.get("pest_level", "")
        if pest in ["fungal_blight", "rust"]:
            return "apply_fungicide"
        return "apply_pesticide_organic"
    if obs.get("soil_moisture", 0.5) < 0.3 and obs.get("weather") != "flood_risk":
        return "irrigate"
    if obs.get("soil_nitrogen", 0.5) < 0.3:
        return "apply_fertilizer_nitrogen"
    if obs.get("soil_phosphorus", 0.5) < 0.3:
        return "apply_fertilizer_phosphorus"
    if obs.get("days_to_harvest", 999) <= 5:
        return "harvest"
    if obs.get("crop_health", 1.0) < 0.5:
        return "prune"
    return "skip_day"

# ─── LLM Agent ────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert agricultural advisor. Given farm state, choose the best action.

VALID ACTIONS: irrigate, apply_fertilizer_nitrogen, apply_fertilizer_phosphorus,
apply_pesticide_chemical, apply_pesticide_organic, apply_fungicide, harvest,
skip_day, soil_test, consult_weather, plant_cover_crop, prune, mulch

Respond ONLY with a single action string. Nothing else."""

def get_llm_action(observation: dict) -> str:
    try:
        client = OpenAI(
            base_url=API_BASE_URL,
            api_key=HF_TOKEN if HF_TOKEN else "no-key-needed",
        )
        obs_text = json.dumps(observation, indent=2)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Farm state:\n{obs_text}\n\nBest action?"}
            ],
            max_tokens=20,
            temperature=0.1,
        )
        action = response.choices[0].message.content.strip().lower().replace('"','').replace("'","")
        if action in observation.get("valid_actions", []):
            return action
    except Exception as e:
        print(json.dumps({"type": "WARN", "message": f"LLM failed: {str(e)}, using rule-based"}))
    return rule_based_fallback(observation)

# ─── Main Inference Loop ───────────────────────────────────────────────────────
def run_inference():
    MAX_STEPS = 50
    total_reward = 0.0

    # Wait for Space to be ready before starting
    wait_for_space(retries=10, delay=6)

    print(json.dumps({
        "type": "START",
        "model": MODEL_NAME,
        "environment": "KisanEnv",
        "max_steps": MAX_STEPS
    }))

    reset_result = env_reset()
    observation  = reset_result.get("observation", {})
    step_num     = 0

    for step_num in range(MAX_STEPS):
        action = get_llm_action(observation)
        result = env_step(action)

        observation  = result.get("observation", {})
        reward       = result.get("reward", 0.0)
        done         = result.get("done", False)
        info         = result.get("info", {})
        total_reward += reward

        print(json.dumps({
            "type":          "STEP",
            "step":          step_num + 1,
            "action":        action,
            "reward":        reward,
            "done":          done,
            "crop_health":   observation.get("crop_health"),
            "soil_moisture": observation.get("soil_moisture"),
            "pest_level":    observation.get("pest_level"),
            "days_to_harvest": observation.get("days_to_harvest"),
            "info":          info
        }))

        if done:
            break

    # Fetch grader scores
    easy_score = medium_score = hard_score = 0.0
    try:
        easy_score   = requests.get(f"{API_BASE_URL}/grade/easy",   timeout=10).json().get("score", 0)
        medium_score = requests.get(f"{API_BASE_URL}/grade/medium", timeout=10).json().get("score", 0)
        hard_score   = requests.get(f"{API_BASE_URL}/grade/hard",   timeout=10).json().get("score", 0)
    except Exception as e:
        print(json.dumps({"type": "WARN", "message": f"Grader fetch failed: {str(e)}"}))

    print(json.dumps({
        "type":         "END",
        "total_reward": round(total_reward, 4),
        "steps_taken":  step_num + 1,
        "scores": {
            "easy":   round(easy_score,   4),
            "medium": round(medium_score, 4),
            "hard":   round(hard_score,   4),
        },
        "final_observation": {
            "crop_health":     observation.get("crop_health"),
            "harvest_done":    observation.get("harvest_done"),
            "days_to_harvest": observation.get("days_to_harvest"),
        }
    }))


if __name__ == "__main__":
    run_inference()
