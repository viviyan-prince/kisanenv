---
title: KisanEnv
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: docker
pinned: false
tags:
  - openenv
---

# 🌾 KisanEnv — Agricultural Advisory OpenEnv Environment

**KisanEnv** is a real-world OpenEnv environment simulating the daily decisions of an agricultural advisor working with Indian farmers. An AI agent must manage crop health, irrigation, pest control, and nutrient levels across a full growing season to maximize yield.

## 🎯 The Task

Build an AI agent that can advise on:
- **When and how much** to irrigate given weather/soil conditions
- **Which pesticide** to use for specific pests (chemical vs organic vs fungicide)  
- **Nutrient management** — when nitrogen/phosphorus levels are deficient
- **Harvest timing** — not too early, not too late

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Start a new farming season |
| `POST` | `/step` | Take an action `{"action": "irrigate"}` |
| `GET`  | `/state` | Get current farm state |
| `GET`  | `/openenv/validate` | Validate OpenEnv compliance |
| `GET`  | `/grade/easy` | Score: Irrigation management |
| `GET`  | `/grade/medium` | Score: Pest & nutrient control |
| `GET`  | `/grade/hard` | Score: Full season yield |

## 📊 Observation Space

```json
{
  "day": 12,
  "crop": "rice",
  "soil_type": "clay",
  "season": "kharif",
  "weather": "sunny",
  "soil_moisture": 0.28,
  "soil_nitrogen": 0.45,
  "soil_phosphorus": 0.60,
  "pest_level": "fungal_blight",
  "crop_health": 0.72,
  "days_to_harvest": 108,
  "warnings": ["CRITICAL: Low soil moisture", "ALERT: fungal_blight infestation"],
  "harvest_done": false,
  "valid_actions": ["irrigate", "apply_pesticide_chemical", ...]
}
```

## ⚡ Action Space (13 actions)

| Action | Effect |
|--------|--------|
| `irrigate` | Increase soil moisture |
| `apply_fertilizer_nitrogen` | Add nitrogen |
| `apply_fertilizer_phosphorus` | Add phosphorus |
| `apply_pesticide_chemical` | Eliminate pests (reliable) |
| `apply_pesticide_organic` | Eliminate pests (eco, 70% success) |
| `apply_fungicide` | Target fungal/rust diseases |
| `harvest` | Harvest crop (only valid near maturity) |
| `soil_test` | Reveal exact nutrient levels |
| `consult_weather` | Get weather forecast |
| `plant_cover_crop` | Improve long-term soil health |
| `prune` | Improve crop health |
| `mulch` | Retain moisture |
| `skip_day` | Do nothing |

## 🏆 Tasks & Graders

### Easy: Irrigation Management (0–1.0)
Keep soil moisture above 0.4. Avoid over-irrigation and flood-risk errors.

### Medium: Pest & Nutrient Control (0–1.0)  
Maintain crop health above 0.7 through correct pest treatment and nutrient management.

### Hard: Full Season Yield (0–1.0)
Complete a full growing season (75–300 days depending on crop) with maximum yield score.

## 🎯 Reward Function

- Correct irrigation timing: **+0.15**
- Eliminating pest correctly: **+0.25 to +0.30**
- Unnecessary action: **-0.05 to -0.10**
- Premature harvest: **-0.30**
- Successful harvest: **up to +1.0** (based on crop health × moisture)
- Crop death: **-0.50**

## 🚀 Setup & Running

```bash
docker build -t kisanenv .
docker run -p 7860:7860 kisanenv
```

## 📝 Baseline Inference

```bash
export API_BASE_URL="https://your-space.hf.space"
export MODEL_NAME="your-model-name"
export HF_TOKEN="your-hf-token"
python inference.py
```

Expected baseline score: Easy ~0.65, Medium ~0.50, Hard ~0.35

## 🌱 Domain Relevance

India has 140M+ farming households. Precision agricultural advisory is a critical real-world AI problem. This environment models actual decision-making challenges that agricultural extension workers and advisory apps face daily.
