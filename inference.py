"""
KisanEnv — Baseline Inference Script
Follows the EXACT OpenEnv hackathon format with START/STEP/END logs.
Uses the OpenAI client (configured via environment variables) as the LLM backbone.
"""

import os
import json
import requests
from openai import OpenAI

# ─── Environment Configuration (REQUIRED) ─────────────────────────────────────
API_BASE_URL     = os.getenv("API_BASE_URL", "<your-active-space-url>")
MODEL_NAME       = os.getenv("MODEL_NAME",   "<your-active-model-name>")
HF_TOKEN         = os.getenv("HF_TOKEN")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# ─── Helper: Call the environment ─────────────────────────────────────────────
def env_reset():
    resp = requests.post(f"{API_BASE_URL}/reset", timeout=30)
    resp.raise_for_status()
    return resp.json()

def env_step(action: str):
    resp = requests.post(
        f"{API_BASE_URL}/step",
        json={"action": action},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()

def env_state():
    resp = requests.get(f"{API_BASE_URL}/state", timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── Rule-based fallback (used when LLM fails) ────────────────────────────────
def rule_based_fallback(obs: dict) -> str:
    if obs.get("pest_level", "none") != "none":
        pest = obs["pest_level"]
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
        # Create client inside function so it only runs when env vars are set
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
        action = response.choices[0].message.content.strip().lower().replace('"', '').replace("'", "")
        valid_actions = observation.get("valid_actions", [])
        if action in valid_actions:
            return action
    except Exception as e:
        print(json.dumps({"type": "WARN", "message": f"LLM failed: {str(e)}, using rule-based"}))
    return rule_based_fallback(observation)

# ─── Main Inference Loop ───────────────────────────────────────────────────────
def run_inference():
    MAX_STEPS = 50
    total_reward = 0.0

    print(json.dumps({
        "type": "START",
        "model": MODEL_NAME,
        "environment": "KisanEnv",
        "max_steps": MAX_STEPS
    }))

    try:
        reset_result = env_reset()
    except Exception as e:
        print(json.dumps({"type": "ERROR", "message": f"Reset failed: {str(e)}"}))
        raise

    observation = reset_result.get("observation", {})
    step_num = 0

    for step_num in range(MAX_STEPS):
        action = get_llm_action(observation)

        try:
            result = env_step(action)
        except Exception as e:
            print(json.dumps({"type": "ERROR", "step": step_num + 1, "message": str(e)}))
            break

        observation = result.get("observation", {})
        reward      = result.get("reward", 0.0)
        done        = result.get("done", False)
        info        = result.get("info", {})
        total_reward += reward

        print(json.dumps({
            "type": "STEP",
            "step": step_num + 1,
            "action": action,
            "reward": reward,
            "done": done,
            "crop_health":      observation.get("crop_health"),
            "soil_moisture":    observation.get("soil_moisture"),
            "pest_level":       observation.get("pest_level"),
            "days_to_harvest":  observation.get("days_to_harvest"),
            "info": info
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
        "type": "END",
        "total_reward": round(total_reward, 4),
        "steps_taken": step_num + 1,
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
