<h1 align="center">TripGenie</h1>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776ab.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-multi--agent-7657d9.svg" alt="LangGraph">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg" alt="License"></a>
  <a href="https://github.com/Aditya-jakhmola/TripGenie/actions/workflows/tests.yml"><img src="https://github.com/Aditya-jakhmola/TripGenie/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
</p>

<p align="center">
  A multi-agent AI travel planner. Describe a trip in plain English and get
  flights, hotels, attractions, weather, a route-aware day-by-day itinerary,
  a budget breakdown and a packing list, with live progress while it works.
</p>

<p align="center"><img src="docs/home.png" width="800" alt="TripGenie home page"></p>
<p align="center"><img src="docs/plan.png" width="800" alt="A finished trip plan with budget breakdown"></p>
<p align="center"><img src="docs/map.png" width="800" alt="Route map and packing list"></p>

 **Live demo:** https://tripgenie-fy38.onrender.com/ (free hosting: the first visit after a quiet period can take about a minute to wake up)
---

## Table of Contents

- [About](#about)
- [How it works](#how-it-works)
- [Features](#features)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Credits and license](#credits-and-license)

## About

Planning a trip usually means juggling a pile of browser tabs: one for flights,
one for hotels, one for the weather, and a notes app to make sense of it all.
TripGenie collapses that into one request. You write something like
*"Plan a 7 day trip to Bali"*, and a pipeline of specialised AI agents
researches each part of the trip and assembles the results into a single plan.

## How it works

Each request runs through a **9-step LangGraph pipeline**. Every step is a
separate agent that reads and writes a shared state:

```mermaid
flowchart LR
    A[Flights] --> B[Hotels] --> C[Attractions] --> D[Route] --> E[Weather]
    E --> F[Itinerary] --> G[Packing] --> H[Budget] --> I[Final answer]
```

| Agent | What it does | Data source |
|---|---|---|
| **Flights** | Airport and airline guidance for the route | AviationStack (via MCP) + LLM |
| **Hotels** | Accommodation options for the destination | Tavily web search (via MCP) |
| **Attractions** | Top things to see and do | Tavily web search (via MCP) |
| **Route** | Extracts named places, geocodes them, and clusters them into day groups by real distance | OpenStreetMap Nominatim + k-means |
| **Weather** | Current conditions and forecast | OpenWeather (via MCP) |
| **Itinerary** | Day-by-day plan that follows the route groupings | LLM |
| **Packing** | Checklist based on weather, activities and trip length | Rules-based (no LLM call) |
| **Budget** | Structured cost estimate, compared to your budget if you give one | LLM (JSON output) |
| **Final** | Assembles everything into the formatted answer | LLM |

Progress is **streamed live** to the browser over Server-Sent Events, so you see
each step complete instead of waiting on a single spinner.

## Features

- **Multi-agent planning** across flights, hotels, attractions, weather, itinerary, packing and budget
- **Live progress checklist** driven by real pipeline events, not a fake timer
- **Route-aware itineraries**: attractions are geocoded and grouped by proximity so each day makes geographic sense
- **Interactive route map** (Leaflet + OpenStreetMap) with day-coloured pins
- **Budget breakdown card** with a within/over-budget indicator
- **Tick-off packing list** tailored to the trip
- **Accounts and profiles**: sign up, log in, rename yourself, and keep your trip history
- **Trip history** that works anonymously per device and per account once logged in
- **Destination search**: browse popular places or search any city, state or country, with real photos from Wikipedia
- **Trip builder form** if you'd rather fill in fields than write a sentence
- **Copy, download as Markdown, or print** any plan
- **Light and dark themes**
- **Graceful degradation**: if a data source fails or is rate limited, that section reports it and the rest of the plan still completes
- **Optional Redis caching** to avoid repeating slow external calls

## Tech stack

**Backend:** Python 3.11+, FastAPI, LangGraph, LangChain (Groq), Model Context
Protocol (MCP) adapters, PostgreSQL (psycopg), Redis (optional)

**Frontend:** Vanilla JavaScript, HTML and CSS served by FastAPI. No build step.
Leaflet for maps.

**External services:** Groq (LLM), Tavily (search), AviationStack (aviation
data), OpenWeather (weather), OpenStreetMap Nominatim (geocoding), Wikipedia
(destination photos)

## Getting started

### Prerequisites

- **Python 3.11 or newer**
- **[uv](https://docs.astral.sh/uv/)** for dependency management
- **A PostgreSQL database**. A free [Render](https://render.com/) instance works.
  It stores LangGraph checkpoints, trip history and user accounts.
- **API keys** (all have free tiers):
  [Groq](https://console.groq.com/), [Tavily](https://tavily.com/),
  [OpenWeather](https://openweathermap.org/api) and optionally
  [AviationStack](https://aviationstack.com/)

### Installation

```bash
git clone https://github.com/Aditya-jakhmola/TripGenie.git
cd <your-repo-name>
uv sync
```

Create a `.env` file in the project root (see [Configuration](#configuration)),
then start the app:

```bash
uv run python app.py
```

Open **<http://127.0.0.1:8000>**. If the top bar shows a green **API connected**
indicator, you're ready to plan a trip.

## Configuration

Create a `.env` file in the project root. It is ignored by Git, so never commit
real keys.

```dotenv
# Required
GROQ_API_KEY=your_groq_key
DATABASE_URL=postgresql://user:password@host:5432/dbname
AUTH_SECRET_KEY=a_long_random_string

# Data sources
TAVILY_API_KEY=your_tavily_key
OPENWEATHER_API_KEY=your_openweather_key
AVIATIONSTACK_API_KEY=your_aviationstack_key

# Optional
GROQ_MODEL=openai/gpt-oss-20b
GEOCODE_USER_AGENT=TripGenie/1.0 (your-email@example.com)
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
```

| Variable | Required | Purpose |
|---|:---:|---|
| `GROQ_API_KEY` | Yes | Powers the LLM agents |
| `DATABASE_URL` | Yes | PostgreSQL for checkpoints, trips and users |
| `AUTH_SECRET_KEY` | Yes | Signs login tokens. Keep it stable; changing it logs everyone out |
| `TAVILY_API_KEY` | Yes | Hotel and attraction search |
| `OPENWEATHER_API_KEY` | Yes | Weather and forecast |
| `AVIATIONSTACK_API_KEY` | Recommended | Airport and airline reference data. Without it, the flights section reports that it is unavailable and the rest of the plan still works |
| `GROQ_MODEL` | No | Swap the model without editing code |
| `GEOCODE_USER_AGENT` | No | Identifies your app to OpenStreetMap, as their usage policy requires. Set your own contact |
| `REDIS_URL` | No | Enables caching. Leave unset to run without a cache |
| `LOG_LEVEL` | No | `INFO` (default) or `DEBUG` |

Generate a good `AUTH_SECRET_KEY` with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Usage

1. Type a request, click a **popular destination**, or open **View All** to search any place.
2. Watch the checklist as each agent finishes.
3. Read the plan, check the **Budget Breakdown**, explore the **Trip Route Map**, and tick off the **Packing List**.
4. **Sign up** from the account icon to keep your trips. **My Trips** reopens any saved plan.

Prefer fields to sentences? Click the sliders icon next to the message box to
open the trip builder, then choose **Write my prompt**.

   ### Running the tests

```bash
   uv run python -m unittest discover -s tests -t . -v
```

## Troubleshooting

<details>
<summary><b>"Rate limit reached" or "Request too large" errors</b></summary>

These come from Groq's free tier, which caps tokens per minute. One trip makes
several LLM calls back to back, so a busy minute can hit the limit. The app
retries automatically and the limits reset every minute. If it keeps happening,
wait a minute, or lower `AIRPORT_DATA_CHAR_LIMIT`, `AIRLINE_DATA_CHAR_LIMIT` and
`TAVILY_RESULT_CHAR_LIMIT` to send smaller prompts.
</details>

<details>
<summary><b>"failed to resolve host" for the database</b></summary>

Your `DATABASE_URL` points at a host your machine cannot reach (for example the
Docker-internal hostname `postgres`). Use the **External** connection URL from
your database provider. Also check that no `DATABASE_URL` is already set in your
terminal session, since that takes priority over `.env`.
</details>

<details>
<summary><b>I get logged out whenever I restart the server</b></summary>

Make sure `AUTH_SECRET_KEY` is set in `.env` and doesn't change between runs.
</details>

<details>
<summary><b>The page looks stale after an update</b></summary>

Hard refresh with `Ctrl+Shift+R`.
</details>

<details>
<summary><b>Some destination cards have no photo</b></summary>

Photos come from Wikipedia, and smaller places may not have one. Those cards
show a location icon instead.
</details>

## Known limitations

These are deliberate scope choices, listed so you know what to change before
running this at scale:

- **Free-tier dependencies.** Groq, Nominatim (about 1 request per second) and
  the data APIs all have rate limits that a busy public deployment would hit.
- **Stateless login tokens.** Sessions survive restarts, but logging out only
  clears the cookie, because there is no server-side revocation list.
- **Flight information is guidance, not live fares.** It is not a booking engine.
- **Anonymous trips are not merged into an account.** Trips saved before logging
  in stay tied to the device.

## Roadmap

- Public deployment (backend on Render, frontend on Vercel)
- Real-time alerts
- Mobile app

## Credits and license

TripGenie is **based on [TravelBrain](https://github.com/KalyanM45/TravelBrain-Multi-Agent-AI-Travel-Planner)
by KalyanM45**, used and modified under the GPL-3.0.

**Changes in this version** by Aditya Jakhmola (2026):

- Renamed and rebranded to TripGenie, with a redesigned landing page and UI
- Added the attractions, route, packing and budget agents
- Added route-aware itineraries with geocoding, clustering and an interactive map
- Added live streaming progress over Server-Sent Events
- Added user accounts, profiles and per-user trip history
- Added destination search with Wikipedia photos
- Added retry and graceful-degradation handling across agents

Thanks also to [Groq](https://groq.com/), [Tavily](https://tavily.com/),
[AviationStack](https://aviationstack.com/), [OpenWeather](https://openweathermap.org/),
[OpenStreetMap](https://www.openstreetmap.org/) and [Leaflet](https://leafletjs.com/).

Licensed under the **GNU General Public License v3.0**. See [LICENSE](LICENSE).
