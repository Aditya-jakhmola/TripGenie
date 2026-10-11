import os
from pathlib import Path
import traceback
import uvicorn
import logging
import uuid
import asyncio
import queue as queue_module
import threading

from dotenv import load_dotenv
load_dotenv()

_LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=_LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tripgenie")

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.api.sessions import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    clear_credentials,
    get_credentials_for,
    new_session_id,
    store_credentials,
)
from src.api.validation import check_database_url, check_groq_api_key
from src.clients import cache
from src.config.session import (
    MissingCredentialsError,
    credential_status,
    use_credentials,
)
from src.config.settings import COOKIE_SAMESITE, COOKIE_SECURE, CORS_ORIGINS, AUTH_COOKIE, AUTH_SESSION_TTL_SECONDS
from src.graph.runner import run_travel_agent, stream_travel_agent
from src.clients.trips_db import delete_trip, get_trip, list_trips, save_trip
from src.auth.auth_sessions import create_auth_session, delete_auth_session, get_user_id_for_token
from src.auth.users_db import EmailAlreadyExists, create_user, get_user_by_id, update_display_name, verify_login
from src.utils.geocode import search_places, wikipedia_thumbnail

# This is to allow nested event loops for async calls in FastAPI
import nest_asyncio
nest_asyncio.apply()


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"




app = FastAPI(
    title="TripGenie AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0"
)


# Only needed when the browser talks to this API on a different origin. With
# the Vercel rewrite the frontend is same-origin, so this stays inactive.
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="static"
)


templates = Jinja2Templates(
    directory=str(FRONTEND_DIR / "templates")
)



class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ConfigRequest(BaseModel):
    """
    None leaves a field untouched, "" clears it. Keys are held in server
    memory for this session only and are never echoed back.
    """

    groq_api_key: str | None = None
    database_url: str | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateProfileRequest(BaseModel):
    display_name: str



def _session_id(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )


TRIP_DEVICE_COOKIE = "tripgenie_device"


def _device_id(request: Request):
    existing = request.cookies.get(TRIP_DEVICE_COOKIE)

    if existing:
        return existing, False

    return str(uuid.uuid4()), True


def _set_device_cookie(response: Response, device_id: str) -> None:
    response.set_cookie(
        key=TRIP_DEVICE_COOKIE,
        value=device_id,
        max_age=365 * 24 * 3600,
        httponly=True,
        samesite="lax",
    )


def _auth_token(request: Request) -> str | None:
    return request.cookies.get(AUTH_COOKIE)


def _current_user_id(request: Request):
    token = _auth_token(request)
    return get_user_id_for_token(token) if token else None


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE,
        value=token,
        max_age=AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE)


def _resolve_owner_key(request: Request):
    """
    Returns (owner_key, device_id_to_set_or_None). owner_key is
    'user:<id>' once someone is logged in, otherwise 'device:<uuid>'
    from the existing anonymous cookie - trip history keeps working
    exactly as before for anyone who never logs in.
    """

    user_id = _current_user_id(request)

    if user_id is not None:
        return f"user:{user_id}", None

    device_id, is_new_device = _device_id(request)

    return f"device:{device_id}", (device_id if is_new_device else None)


def _sse_event(event: str, data: dict) -> str:
    import json
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )

    # Prevent the browser from ever serving a stale cached copy of the
    # page shell - this is what caused an old UI to flash on some
    # refreshes and not others.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"

    return response


# =========================
# Credentials
# =========================

@app.get("/api/config")
async def read_config(request: Request):
    """What is configured, and where it came from. Never returns a secret."""

    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        return JSONResponse(content=credential_status())


@app.post("/api/config")
async def write_config(request: Request, body: ConfigRequest):
    """
    Store credentials for this browser session. Each supplied value is
    checked against the real service before being accepted.
    """

    session_id = _session_id(request) or new_session_id()

    errors = {}

    groq_key = (body.groq_api_key or "").strip()
    if groq_key:
        ok, detail = check_groq_api_key(groq_key)
        if not ok:
            errors["groq_api_key"] = detail

    database_url = (body.database_url or "").strip()
    if database_url:
        ok, detail = check_database_url(database_url)
        if not ok:
            errors["database_url"] = detail

    if errors:
        response = JSONResponse(
            status_code=400,
            content={"success": False, "errors": errors},
        )
        _set_session_cookie(response, session_id)
        return response

    credentials = store_credentials(
        session_id,
        groq_api_key=body.groq_api_key,
        database_url=body.database_url,
    )

    with use_credentials(credentials):
        payload = {"success": True, **credential_status()}

    response = JSONResponse(content=payload)
    _set_session_cookie(response, session_id)

    return response


@app.delete("/api/config")
async def reset_config(request: Request):
    """Drop session keys and fall back to whatever the server's .env has."""

    clear_credentials(_session_id(request))

    with use_credentials(None):
        return JSONResponse(content={"success": True, **credential_status()})


# =========================
# Destination search
# =========================

POPULAR_DESTINATIONS = [
    ("Bali", "Indonesia"),
    ("Paris", "France"),
    ("Tokyo", "Japan"),
    ("Santorini", "Greece"),
    ("New York City", "United States"),
    ("Rome", "Italy"),
    ("Dubai", "United Arab Emirates"),
    ("Sydney", "Australia"),
    ("Barcelona", "Spain"),
    ("Cape Town", "South Africa"),
    ("Kyoto", "Japan"),
    ("Reykjavik", "Iceland"),
]


@app.get("/api/destinations/popular")
async def popular_destinations():
    results = []

    for name, country in POPULAR_DESTINATIONS:
        try:
            image = wikipedia_thumbnail(name)
        except Exception:
            image = None

        results.append({
            "name": name,
            "subtitle": country,
            "display_name": f"{name}, {country}",
            "image": image,
        })

    return JSONResponse(content={"results": results})


@app.get("/api/destinations/search")
async def search_destinations(q: str = ""):
    query = q.strip()

    if len(query) < 2:
        return JSONResponse(content={"results": []})

    try:
        places = search_places(query)
    except Exception as e:
        logger.warning("Destination search failed: %s", e)
        places = []

    results = []

    for place in places:
        try:
            image = wikipedia_thumbnail(place["name"])
        except Exception:
            image = None

        results.append({
            "name": place["name"],
            "subtitle": place["country"],
            "display_name": place["display_name"],
            "image": image,
        })

    return JSONResponse(content={"results": results})


# =========================
# Planning
# =========================

@app.post("/api/travel")
async def travel_planner(request: Request, request_data: TravelRequest):
    credentials = get_credentials_for(_session_id(request))

    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )

        with use_credentials(credentials):
            result = run_travel_agent(
                user_input=user_message,
                thread_id=request_data.thread_id
            )

        response_content = {
            "success": True,
            "thread_id": result["thread_id"],
            "answer": result["answer"],
            "flight_results": result["flight_results"],
            "hotel_results": result["hotel_results"],
            "attraction_results": result.get("attraction_results", ""),
            "weather_results": result.get("weather_results", ""),
            "itinerary": result["itinerary"],
            "budget_estimate": result.get("budget_estimate", {}),
            "trip_days": result.get("trip_days", 0),
            "route_plan": result.get("route_plan", {}),
            "packing_list": result.get("packing_list", {}),
            "llm_calls": result["llm_calls"],
        }

        response = JSONResponse(content=response_content)

        try:
            owner_key, new_device_id = _resolve_owner_key(request)

            save_trip(
                owner_key,
                result["thread_id"],
                request_data.message,
                result["answer"],
            )

            if new_device_id:
                _set_device_cookie(response, new_device_id)
        except Exception as e:
            logger.warning("Could not save trip history: %s", e)

        return response

    except MissingCredentialsError as e:
        # The frontend turns this into a prompt to open Settings.
        return JSONResponse(
            status_code=428,
            content={
                "success": False,
                "error": str(e),
                "missing": e.missing,
            }
        )

    except Exception as e:
        logger.exception("Travel planner run failed: %s", e)


        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

@app.post("/api/travel/stream")
async def travel_planner_stream(request: Request, request_data: TravelRequest):
    """
    Same work as /api/travel, but streamed as Server-Sent Events: one
    'step' event per agent as it finishes, then one 'done' event with
    the same payload shape /api/travel returns in one shot.
    """

    credentials = get_credentials_for(_session_id(request))
    user_message = request_data.message.strip()

    if not user_message:
        def _empty_error():
            yield _sse_event(
                "error",
                {"success": False, "error": "Message cannot be empty."},
            )

        return StreamingResponse(_empty_error(), media_type="text/event-stream")

    owner_key, new_device_id = _resolve_owner_key(request)

    async def _generate():
        # Some browsers buffer the first chunk of a stream until a
        # minimum size is reached, so tiny early events can get held
        # back until the connection closes. This comment line is
        # ignored by SSE parsers but pushes past that threshold
        # immediately, so real events start flushing right away.
        yield ": " + (" " * 2048) + "\n\n"

        loop = asyncio.get_event_loop()
        event_queue: queue_module.Queue = queue_module.Queue()
        SENTINEL = object()

        def worker():
            # Runs on a real background thread, not Starlette's implicit
            # per-next() threadpool relay - each item is pushed onto the
            # queue the instant stream_travel_agent yields it, so the
            # async side below can forward it immediately instead of
            # everything arriving batched at the end.
            with use_credentials(credentials):
                try:
                    for kind, payload in stream_travel_agent(
                        user_input=user_message,
                        thread_id=request_data.thread_id,
                    ):
                        event_queue.put((kind, payload))
                except MissingCredentialsError as e:
                    event_queue.put(("missing_credentials", e))
                except Exception as e:
                    event_queue.put(("exception", e))
                finally:
                    event_queue.put(SENTINEL)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            item = await loop.run_in_executor(None, event_queue.get)

            if item is SENTINEL:
                break

            kind, payload = item

            if kind == "step":
                yield _sse_event("step", {"node": payload})

            elif kind == "done":
                result = payload

                try:
                    save_trip(
                        owner_key,
                        result["thread_id"],
                        user_message,
                        result["answer"],
                    )
                except Exception as e:
                    logger.warning("Could not save trip history: %s", e)

                yield _sse_event("done", {"success": True, **result})

            elif kind == "missing_credentials":
                e = payload
                yield _sse_event(
                    "error",
                    {
                        "success": False,
                        "error": str(e),
                        "missing": e.missing,
                        "code": 428,
                    },
                )

            elif kind == "exception":
                e = payload
                logger.exception("Streaming travel planner run failed: %s", e)
                yield _sse_event("error", {"success": False, "error": str(e)})

    response = StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

    if new_device_id:
        _set_device_cookie(response, new_device_id)

    return response


@app.post("/api/auth/register")
async def register(request_data: RegisterRequest):
    email = request_data.email.strip()
    password = request_data.password

    if not email or "@" not in email:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Enter a valid email address."},
        )

    if len(password) < 8:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Password must be at least 8 characters."},
        )

    try:
        user = create_user(email, password, request_data.display_name)
    except EmailAlreadyExists:
        return JSONResponse(
            status_code=409,
            content={"success": False, "error": "An account with that email already exists."},
        )
    except Exception as e:
        logger.exception("Registration failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Could not create account."},
        )

    token = create_auth_session(user["id"])
    response = JSONResponse(content={"success": True, "user": user})
    _set_auth_cookie(response, token)
    return response


@app.post("/api/auth/login")
async def login(request_data: LoginRequest):
    user = verify_login(request_data.email, request_data.password)

    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Incorrect email or password."},
        )

    token = create_auth_session(user["id"])
    response = JSONResponse(content={"success": True, "user": user})
    _set_auth_cookie(response, token)
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    token = _auth_token(request)

    if token:
        delete_auth_session(token)

    response = JSONResponse(content={"success": True})
    _clear_auth_cookie(response)
    return response


@app.get("/api/auth/me")
async def me(request: Request):
    user_id = _current_user_id(request)

    if user_id is None:
        return JSONResponse(content={"user": None})

    user = get_user_by_id(user_id)
    return JSONResponse(content={"user": user})


@app.post("/api/auth/profile")
async def update_profile(request: Request, request_data: UpdateProfileRequest):
    user_id = _current_user_id(request)

    if user_id is None:
        return JSONResponse(status_code=401, content={"success": False, "error": "Not logged in."})

    name = request_data.display_name.strip()

    if not name:
        return JSONResponse(status_code=400, content={"success": False, "error": "Name cannot be empty."})

    try:
        user = update_display_name(user_id, name)
    except Exception as e:
        logger.exception("Could not update profile: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": "Could not update profile."})

    if not user:
        return JSONResponse(status_code=404, content={"success": False, "error": "User not found."})

    return JSONResponse(content={"success": True, "user": user})


@app.get("/api/trips")
async def get_trips(request: Request):
    user_id = _current_user_id(request)
    device_id = request.cookies.get(TRIP_DEVICE_COOKIE)

    owner_key = (
        f"user:{user_id}" if user_id is not None
        else (f"device:{device_id}" if device_id else None)
    )

    if not owner_key:
        return JSONResponse(content={"trips": []})

    try:
        trips = list_trips(owner_key)
    except Exception as e:
        logger.warning("Could not load trip history: %s", e)
        trips = []

    return JSONResponse(content={"trips": trips})


@app.get("/api/trips/{trip_id}")
async def get_trip_detail(request: Request, trip_id: int):
    user_id = _current_user_id(request)
    device_id = request.cookies.get(TRIP_DEVICE_COOKIE)

    owner_key = (
        f"user:{user_id}" if user_id is not None
        else (f"device:{device_id}" if device_id else None)
    )

    if not owner_key:
        return JSONResponse(status_code=404, content={"error": "Trip not found."})

    try:
        trip = get_trip(owner_key, trip_id)
    except Exception as e:
        logger.warning("Could not load trip: %s", e)
        trip = None

    if not trip:
        return JSONResponse(status_code=404, content={"error": "Trip not found."})

    return JSONResponse(content=trip)


@app.delete("/api/trips/{trip_id}")
async def remove_trip(request: Request, trip_id: int):
    user_id = _current_user_id(request)
    device_id = request.cookies.get(TRIP_DEVICE_COOKIE)

    owner_key = (
        f"user:{user_id}" if user_id is not None
        else (f"device:{device_id}" if device_id else None)
    )

    if not owner_key:
        return JSONResponse(status_code=404, content={"error": "Trip not found."})

    try:
        deleted = delete_trip(owner_key, trip_id)
    except Exception as e:
        logger.warning("Could not delete trip: %s", e)
        deleted = False

    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Trip not found."})

    return JSONResponse(content={"success": True})

@app.head("/", include_in_schema=False)
async def home_head():
    """Hosting platforms probe with HEAD to detect an open port."""

    return Response(status_code=200)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check(request: Request):
    credentials = get_credentials_for(_session_id(request))

    with use_credentials(credentials):
        status = credential_status()

    return {
        "status": "ok",
        "message": "AI Travel Planner API is running",
        "ready": status["ready"],
        "missing": status["missing"],
        "cache": cache.status(),
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})



if __name__ == "__main__":
    # Defaults suit local development. In Docker, HOST is set to 0.0.0.0
    # so the port is reachable from outside the container.
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() not in ("false", "0", "no")
    )