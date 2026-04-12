---
title: KisanEnv
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
tags:
  - openenv
---

# 🌾 KisanEnv — Agricultural Advisory OpenEnv Environment

Real-world OpenEnv environment simulating agricultural advisory decisions.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reset` | Start new farming season |
| `POST` | `/step` | Take action `{"action": "irrigate"}` |
| `GET`  | `/state` | Current farm state |
| `GET`  | `/openenv/validate` | OpenEnv compliance check |
| `GET`  | `/grade/easy` | Irrigation management score |
| `GET`  | `/grade/medium` | Pest & nutrient score |
| `GET`  | `/grade/hard` | Full season yield score |

## Actions

irrigate, apply_fertilizer_nitrogen, apply_fertilizer_phosphorus,
apply_pesticide_chemical, apply_pesticide_organic, apply_fungicide,
harvest, skip_day, soil_test, consult_weather, plant_cover_crop, prune, mulch

## Setup

```bash
docker build -t kisanenv .
docker run -p 7860:7860 kisanenv
```
