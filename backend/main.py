import math
import os

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Reads DATABASE_URL (and other settings) from the .env file when running locally.
load_dotenv()

app = FastAPI(title="Delivery Route Optimizer")

# The React app is allowed to call this API.
# FRONTEND_URL is set on Render after the frontend is deployed.
allowed_origins = ["http://localhost:5173"]
frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if frontend_url != "":
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Radius of the Earth in km, used in the Haversine formula.
Earth_Radius = 6371.0088

# How important each priority is. A bigger number means a late arrival hurts more.
Priority_Weight = {"HIGH": 4, "MEDIUM": 2, "LOW": 1}

# The assignment says at most 10 deliveries.
Max_Deliveries = 10


@app.get("/health")
def health_check():
    return {"status": "ok"}


def check_coordinates(latitude, longitude):
    """Makes sure latitude and longitude are proper numbers in the allowed range.
    Returns them as floats, or raises ValueError with a message the user can read."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("Latitude and longitude must be numbers")

    # float() accepts "nan" and "inf", but those are not real coordinates.
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        raise ValueError("Latitude and longitude must be finite numbers")

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180")

    return latitude, longitude


def calculate_distance(lat1, lon1, lat2, lon2):
    """Straight-line distance in km between two points on the Earth (Haversine)."""
    lat1, lon1 = check_coordinates(lat1, lon1)
    lat2, lon2 = check_coordinates(lat2, lon2)

    # The formula works with radians, not degrees.
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lat_gap = math.radians(lat2 - lat1)
    lon_gap = math.radians(lon2 - lon1)

    haversine_value = (math.sin(lat_gap / 2) ** 2
                       + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(lon_gap / 2) ** 2)

    # Because of rounding this can end up a tiny bit above 1,
    # and asin would crash, so we cap it.
    haversine_value = min(1.0, haversine_value)

    return 2 * Earth_Radius * math.asin(math.sqrt(haversine_value))


def distance_table(warehouse, deliveries):
    """Makes a table with the distance between every pair of places.
    Place 0 is the warehouse and places 1..n are the deliveries in the order given.
    For example table[1][2] is the distance from delivery 1 to delivery 2."""
    places = [warehouse] + deliveries

    table = []
    for start in places:
        row = []
        for end in places:
            row.append(calculate_distance(start["latitude"], start["longitude"],
                                          end["latitude"], end["longitude"]))
        table.append(row)

    return table


def route_distance(route, table):
    """Adds up the km of a route like [0, 2, 1, 3, 0] (0 is the warehouse)."""
    total = 0
    for i in range(len(route) - 1):
        total = total + table[route[i]][route[i + 1]]
    return total


def route_cost(route, table, priorities, use_priority):
    """The number we try to make as small as possible.
    Without priority: just the total distance.
    With priority: total distance plus a penalty for reaching important stops late.
    The penalty of a stop is its weight times the km travelled before reaching it."""
    total = route_distance(route, table)

    if not use_priority:
        return total

    penalty = 0
    km_so_far = 0
    for i in range(1, len(route) - 1):
        km_so_far = km_so_far + table[route[i - 1]][route[i]]
        weight = Priority_Weight[priorities[route[i]]]
        penalty = penalty + weight * km_so_far

    return total + penalty


def nearest_neighbor_route(table, priorities, use_priority):
    """Builds a first route: from the current place, always go to the best stop left.
    Normally best means closest. With priority I divide the distance by the weight,
    so an important stop looks closer than it really is."""
    unvisited = list(range(1, len(table)))
    route = [0]
    current = 0

    while len(unvisited) > 0:
        best_stop = unvisited[0]
        best_score = None

        for stop in unvisited:
            score = table[current][stop]
            if use_priority:
                score = score / Priority_Weight[priorities[stop]]

            # Using < (not <=) means on a tie the earlier delivery wins,
            # so the same input always gives the same route.
            if best_score is None or score < best_score:
                best_score = score
                best_stop = stop

        route.append(best_stop)
        unvisited.remove(best_stop)
        current = best_stop

    route.append(0)
    return route


def two_opt(route, table, priorities, use_priority):
    """Improves a route by reversing a part of it and checking if the cost drops.
    Only a real improvement is kept, so the loop always ends.
    The warehouse at the start and the end is never moved."""
    best_route = route[:]
    best_cost = route_cost(best_route, table, priorities, use_priority)

    improved = True
    while improved:
        improved = False

        for i in range(1, len(best_route) - 2):
            for j in range(i + 1, len(best_route) - 1):
                # Copy the route and reverse the stops from position i to j.
                new_route = best_route[:]
                part = new_route[i:j + 1]
                part.reverse()
                new_route[i:j + 1] = part

                new_cost = route_cost(new_route, table, priorities, use_priority)
                if new_cost < best_cost:
                    best_route = new_route
                    best_cost = new_cost
                    improved = True

    return best_route


# ---------- Checking the input ----------

def check_place(place, label, need_priority, problems):
    """Checks one place (warehouse or delivery) and returns a cleaned copy.
    Every mistake found is added to the problems list, with the label in front."""
    if place is None:
        problems.append(label + " is missing")
        return {}
    if not isinstance(place, dict):
        problems.append(label + ": must have a name, latitude and longitude")
        return {}

    cleaned = {}

    name = str(place.get("name") or "").strip()
    if name == "":
        problems.append(label + ": name is missing")
    cleaned["name"] = name

    try:
        latitude, longitude = check_coordinates(place.get("latitude"), place.get("longitude"))
        cleaned["latitude"] = latitude
        cleaned["longitude"] = longitude
    except ValueError as error:
        problems.append(label + ": " + str(error))

    if need_priority:
        priority = str(place.get("priority") or "").strip().upper()
        if priority not in Priority_Weight:
            problems.append(label + ": priority must be HIGH, MEDIUM or LOW")
        cleaned["priority"] = priority

    return cleaned


def check_input(data):
    """Checks the whole request.
    Returns warehouse, deliveries, use_priority and a list of problems.
    If the problems list is not empty, the data must not be used."""
    problems = []

    warehouse = check_place(data.get("warehouse"), "Warehouse", False, problems)

    use_priority = data.get("use_priority", True)
    if not isinstance(use_priority, bool):
        problems.append("use_priority must be true or false")

    deliveries = []
    given = data.get("deliveries")
    if not isinstance(given, list) or len(given) == 0:
        problems.append("Add at least one delivery")
    elif len(given) > Max_Deliveries:
        problems.append("Too many deliveries: the maximum is " + str(Max_Deliveries))
    else:
        number = 1
        for place in given:
            deliveries.append(check_place(place, "Delivery " + str(number), True, problems))
            number = number + 1

    return warehouse, deliveries, use_priority, problems


# ---------- Making the answer ----------

def make_result(warehouse, deliveries, route, table, use_priority):
    """Turns the route (a list of place numbers) into the answer the frontend shows."""
    places = [warehouse] + deliveries
    stops = []
    legs = []
    km_so_far = 0

    for position in range(len(route)):
        place = places[route[position]]

        # Every stop except the first one has a leg coming from the stop before it.
        if position > 0:
            leg_km = table[route[position - 1]][route[position]]
            km_so_far = km_so_far + leg_km
            legs.append({
                "from": places[route[position - 1]]["name"],
                "to": place["name"],
                "distance_km": round(leg_km, 2),
            })

        stops.append({
            "number": route[position],           # 0 is the warehouse, 1..n is the delivery number
            "name": place["name"],
            "priority": place.get("priority"),   # the warehouse has no priority
            "km_from_start": round(km_so_far, 2),
        })

    return {
        "use_priority": use_priority,
        "route": stops,
        "legs": legs,
        "total_distance_km": round(km_so_far, 2),
        "note": "Distances are straight-line (Haversine) distances, not road distances.",
    }


# ---------- Saving to the database ----------

def save_route(stops, total_distance, use_priority):
    """Saves one finished route in the routes table and returns the new row id."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    # Turn the stops into text like "Warehouse -> Shop A -> Shop B -> Warehouse".
    names = []
    for stop in stops:
        names.append(stop["name"])
    route_text = " -> ".join(names)

    connection = psycopg2.connect(database_url, connect_timeout=5)
    try:
        cursor = connection.cursor()

        # Makes the table on the first run, so a fresh database needs no manual setup.
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS routes ("
            "id SERIAL PRIMARY KEY, "
            "route TEXT NOT NULL, "
            "total_distance DOUBLE PRECISION NOT NULL, "
            "priority_used BOOLEAN NOT NULL, "
            "created_at TIMESTAMP NOT NULL DEFAULT NOW())"
        )

        # The %s are placeholders, psycopg2 puts the values in safely.
        # I never build the SQL by joining the values into the text.
        cursor.execute(
            "INSERT INTO routes (route, total_distance, priority_used) "
            "VALUES (%s, %s, %s) RETURNING id",
            (route_text, total_distance, use_priority),
        )
        new_id = cursor.fetchone()[0]
        connection.commit()
        cursor.close()
        return new_id
    finally:
        connection.close()


# ---------- The endpoint ----------

@app.post("/optimize")
def optimize_route(data: dict):
    warehouse, deliveries, use_priority, problems = check_input(data)
    if len(problems) > 0:
        raise HTTPException(status_code=400, detail=problems)

    table = distance_table(warehouse, deliveries)

    # priorities[0] belongs to the warehouse, which has no priority.
    priorities = [None]
    for delivery in deliveries:
        priorities.append(delivery["priority"])

    first_route = nearest_neighbor_route(table, priorities, use_priority)
    route = two_opt(first_route, table, priorities, use_priority)
    result = make_result(warehouse, deliveries, route, table, use_priority)

    # If saving fails we still send the route, but we say clearly that it was NOT saved.
    try:
        result["route_id"] = save_route(result["route"], result["total_distance_km"], use_priority)
        result["saved"] = True
    except Exception as error:
        print("Could not save route:", error)    # the real reason only goes to the server log
        result["saved"] = False
        result["save_error"] = "The route was calculated but could not be saved to the database."

    return result
