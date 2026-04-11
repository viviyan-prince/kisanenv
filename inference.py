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
API_BASE_URL = os.getenv("API_BASE_URL", "<your-active-space-url>")
MODEL_NAME   = os.getenv("MODEL_NAME",   "<your-active-model-name>")
HF_TOKEN     = os.getenv("HF_TOKEN")

# Optional — only if using from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

# ─── LLM Client (REQUIRED: must use OpenAI client via env vars) ────────────────
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "no-key-needed",
)

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

# ─── LLM Agent ────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert agricultural advisor. You will be given the current
state of a farm and must choose the best action to maximize crop yield and health.

VALID ACTIONS:
- irrigate: water the crop
- apply_fertilizer_nitrogen: add nitrogen
- apply_fertilizer_phosphorus: add phosphorus
- apply_pesticide_chemical: eliminate pests (chemical)
- apply_pesticide_organic: eliminate pests (organic, less reliable)
- apply_fungicide: target fungal/rust diseases specifically
- harvest: harvest the crop (only when days_to_harvest <= 10)
- skip_day: do nothing
- soil_test: test soil nutrients
- consult_weather: check weather forecast
- plant_cover_crop: improve long-term soil nitrogen
- prune: improve crop health
- mulch: improve moisture retention

DECISION RULES:
1. If pest_level != "none" → apply pesticide or fungicide
2. If soil_moisture < 0.3 and weather != "flood_risk" → irrigate
3. If soil_nitrogen < 0.3 → apply_fertilizer_nitrogen
4. If soil_phosphorus < 0.3 → apply_fertilizer_phosphorus
5. If days_to_harvest <= 5 → harvest
6. If crop_health < 0.5 → prune or mulch

Respond ONLY with a single valid action string from the list above. Nothing else."""

def get_llm_action(observation: dict) -> str:
    obs_text = json.dumps(observation, indent=2)
    prompt = f"Current farm state:\n{obs_text}\n\nWhat action should be taken?"
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=20,
            temperature=0.1,
        )
        action = response.choices[0].message.content.strip().lower().replace('"', '').replace("'", "")
        # Validate action
        valid_actions = observation.get("valid_actions", [])
        if action in valid_actions:
            return action
        # Fallback: rule-based
        return rule_based_fallback(observation)
    except Exception as e:
        print(json.dumps({"type": "WARN", "message": f"LLM call failed: {e}, using rule-based fallback"}))
        return rule_based_fallback(observation)

def rule_based_fallback(obs: dict) -> str:
    """Rule-based agent as fallback"""
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

# ─── Main Inference Loop ───────────────────────────────────────────────────────
def run_inference():
    MAX_STEPS = 50
    total_reward = 0.0
    scores = []

    # ── START log ─────────────────────────────────────────────────
    print(json.dumps({
        "type": "START",
        "model": MODEL_NAME,
        "environment": "KisanEnv",
        "max_steps": MAX_STEPS
    }))

    # Reset environment
    reset_result = env_reset()
    observation = reset_result.get("observation", {})

    for step_num in range(MAX_STEPS):
        # Choose action
        action = get_llm_action(observation)

        # Take step
        result = env_step(action)
        observation = result.get("observation", {})
        reward = result.get("reward", 0.0)
        done = result.get("done", False)
        info = result.get("info", {})

        total_reward += reward
        scores.append(reward)

        # ── STEP log (REQUIRED FORMAT) ─────────────────────────────
        print(json.dumps({
            "type": "STEP",
            "step": step_num + 1,
            "action": action,
            "reward": reward,
            "done": done,
            "crop_health": observation.get("crop_health"),
            "soil_moisture": observation.get("soil_moisture"),
            "pest_level": observation.get("pest_level"),
            "days_to_harvest": observation.get("days_to_harvest"),
            "info": info
        }))

        if done:
            break

    # Compute final scores from graders
    try:
        easy_score   = requests.get(f"{API_BASE_URL}/grade/easy",   timeout=10).json().get("score", 0)
        medium_score = requests.get(f"{API_BASE_URL}/grade/medium", timeout=10).json().get("score", 0)
        hard_score   = requests.get(f"{API_BASE_URL}/grade/hard",   timeout=10).json().get("score", 0)
    except Exception:
        easy_score = medium_score = hard_score = 0.0

    # ── END log ────────────────────────────────────────────────────
    print(json.dumps({
        "type": "END",
        "total_reward": round(total_reward, 4),
        "steps_taken": step_num + 1,
        "scores": {
            "easy":   round(easy_score, 4),
            "medium": round(medium_score, 4),
            "hard":   round(hard_score, 4),
        },
        "final_observation": {
            "crop_health":      observation.get("crop_health"),
            "harvest_done":     observation.get("harvest_done"),
            "days_to_harvest":  observation.get("days_to_harvest"),
        }
    }))


if __name__ == "__main__":
    run_inference()
