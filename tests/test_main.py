import pytest
from fastapi.testclient import TestClient

from backend.main import (
    app,
    calculate_distance,
    check_coordinates,
    distance_table,
    nearest_neighbor_route,
    route_cost,
    route_distance,
    save_route,
    two_opt,
)


# ---------- Distance tests ----------

def test_same_point_has_zero_distance():
    assert calculate_distance(13.08, 80.27, 13.08, 80.27) == 0


def test_one_degree_of_latitude_is_about_111_km():
    assert calculate_distance(0, 0, 1, 0) == pytest.approx(111.19, rel=0.01)


def test_chennai_to_bangalore_is_roughly_290_km():
    distance = calculate_distance(13.0827, 80.2707, 12.9716, 77.5946)
    assert 280 < distance < 300


def test_distance_is_the_same_in_both_directions():
    forward = calculate_distance(10, 20, 30, 40)
    backward = calculate_distance(30, 40, 10, 20)
    assert forward == pytest.approx(backward)


def test_opposite_sides_of_the_earth_do_not_crash():
    assert calculate_distance(0, 0, 0, 180) == pytest.approx(20015, rel=0.01)


@pytest.mark.parametrize("latitude, longitude", [
    (91, 0), (-91, 0), (0, 181), (0, -181),
    (None, 5), ("abc", 1), (float("nan"), 0), (float("inf"), 0),
])
def test_bad_coordinates_are_rejected(latitude, longitude):
    with pytest.raises(ValueError):
        check_coordinates(latitude, longitude)


def test_table_shape_and_diagonal():
    warehouse = {"latitude": 13.0, "longitude": 80.0}
    deliveries = [
        {"latitude": 13.1, "longitude": 80.1},
        {"latitude": 13.2, "longitude": 80.2},
    ]
    table = distance_table(warehouse, deliveries)

    assert len(table) == 3
    assert all(len(row) == 3 for row in table)
    for i in range(3):
        assert table[i][i] == 0


def test_table_is_symmetric():
    warehouse = {"latitude": 13.0, "longitude": 80.0}
    deliveries = [{"latitude": 13.1, "longitude": 80.1}]
    table = distance_table(warehouse, deliveries)
    assert table[0][1] == pytest.approx(table[1][0])


def test_duplicate_coordinates_stay_separate_nodes():
    warehouse = {"latitude": 13.0, "longitude": 80.0}
    same_spot = {"latitude": 13.1, "longitude": 80.1}
    table = distance_table(warehouse, [same_spot, same_spot])

    assert len(table) == 3     # warehouse + 2 separate deliveries
    assert table[1][2] == 0    # the two duplicates are 0 km apart


def test_delivery_at_warehouse_location_has_zero_distance():
    warehouse = {"latitude": 13.0, "longitude": 80.0}
    table = distance_table(warehouse, [{"latitude": 13.0, "longitude": 80.0}])
    assert len(table) == 2
    assert table[0][1] == 0


# ---------- Route tests ----------

# Small table we can check by hand. Place 0 is the warehouse.
HAND_TABLE = [
    [0, 10, 20],
    [10, 0, 10],
    [20, 10, 0],
]


def line_of_places():
    """A warehouse and three deliveries in a straight line."""
    warehouse = {"latitude": 0.0, "longitude": 0.0}
    deliveries = [
        {"latitude": 0.0, "longitude": 0.1},
        {"latitude": 0.0, "longitude": 0.2},
        {"latitude": 0.0, "longitude": 0.3},
    ]
    return warehouse, deliveries


def check_route(route, number_of_deliveries):
    """Route must start and end at the warehouse and visit each delivery once."""
    assert route[0] == 0
    assert route[-1] == 0
    middle = sorted(route[1:-1])
    assert middle == list(range(1, number_of_deliveries + 1))


def test_route_distance_adds_all_legs():
    # 0 -> 1 -> 2 -> 0 is 10 + 10 + 20
    assert route_distance([0, 1, 2, 0], HAND_TABLE) == 40


def test_cost_without_priority_is_just_distance():
    priorities = [None, "HIGH", "LOW"]
    assert route_cost([0, 2, 1, 0], HAND_TABLE, priorities, False) == 40


def test_priority_cost_by_hand():
    priorities = [None, "HIGH", "LOW"]
    # Route 0,1,2,0: distance 40.
    # Stop 1 is HIGH, reached after 10 km: 4 * 10 = 40.
    # Stop 2 is LOW, reached after 20 km: 1 * 20 = 20.
    # Cost = 40 + 40 + 20 = 100
    assert route_cost([0, 1, 2, 0], HAND_TABLE, priorities, True) == 100
    # Route 0,2,1,0: distance 40.
    # Stop 2 is LOW after 20 km: 20. Stop 1 is HIGH after 30 km: 4 * 30 = 120.
    # Cost = 40 + 20 + 120 = 180
    assert route_cost([0, 2, 1, 0], HAND_TABLE, priorities, True) == 180


def test_nearest_neighbor_goes_to_closest_first():
    warehouse, deliveries = line_of_places()
    table = distance_table(warehouse, deliveries)
    priorities = [None, "LOW", "LOW", "LOW"]
    assert nearest_neighbor_route(table, priorities, False) == [0, 1, 2, 3, 0]


def test_nearest_neighbor_prefers_high_priority():
    table = [
        [0, 10, 15],
        [10, 0, 12],
        [15, 12, 0],
    ]
    priorities = [None, "LOW", "HIGH"]
    # Without priority the closer stop (1) goes first.
    assert nearest_neighbor_route(table, priorities, False) == [0, 1, 2, 0]
    # With priority, stop 2 is HIGH: 15 / 4 = 3.75 beats 10 / 1 = 10.
    assert nearest_neighbor_route(table, priorities, True) == [0, 2, 1, 0]


def test_final_route_is_valid_in_both_modes():
    warehouse, deliveries = line_of_places()
    table = distance_table(warehouse, deliveries)
    priorities = [None, "HIGH", "LOW", "MEDIUM"]

    for use_priority in [False, True]:
        first = nearest_neighbor_route(table, priorities, use_priority)
        final = two_opt(first, table, priorities, use_priority)
        check_route(first, 3)
        check_route(final, 3)


def test_single_delivery():
    warehouse = {"latitude": 0.0, "longitude": 0.0}
    deliveries = [{"latitude": 0.0, "longitude": 0.1}]
    table = distance_table(warehouse, deliveries)
    priorities = [None, "HIGH"]

    for use_priority in [False, True]:
        first = nearest_neighbor_route(table, priorities, use_priority)
        final = two_opt(first, table, priorities, use_priority)
        assert first == [0, 1, 0]
        assert final == [0, 1, 0]


def test_two_opt_fixes_a_bad_route():
    warehouse, deliveries = line_of_places()
    table = distance_table(warehouse, deliveries)
    priorities = [None, "LOW", "LOW", "LOW"]

    bad_route = [0, 3, 1, 2, 0]
    cost_before = route_cost(bad_route, table, priorities, False)
    better_route = two_opt(bad_route, table, priorities, False)
    cost_after = route_cost(better_route, table, priorities, False)

    check_route(better_route, 3)
    assert cost_after < cost_before
    # On a straight line the best trip is out to the far end and back.
    assert cost_after == pytest.approx(2 * calculate_distance(0, 0, 0, 0.3))


def test_two_opt_improves_priority_cost():
    priorities = [None, "HIGH", "LOW"]
    bad_route = [0, 2, 1, 0]      # the HIGH stop is visited last
    better_route = two_opt(bad_route, HAND_TABLE, priorities, True)
    assert better_route == [0, 1, 2, 0]


def test_two_opt_never_makes_cost_worse():
    warehouse = {"latitude": 13.08, "longitude": 80.27}
    deliveries = [
        {"latitude": 13.12, "longitude": 80.20},
        {"latitude": 13.00, "longitude": 80.25},
        {"latitude": 13.05, "longitude": 80.30},
        {"latitude": 13.15, "longitude": 80.28},
        {"latitude": 12.98, "longitude": 80.18},
    ]
    table = distance_table(warehouse, deliveries)
    priorities = [None, "HIGH", "LOW", "MEDIUM", "LOW", "HIGH"]

    for use_priority in [False, True]:
        first = nearest_neighbor_route(table, priorities, use_priority)
        final = two_opt(first, table, priorities, use_priority)
        cost_before = route_cost(first, table, priorities, use_priority)
        cost_after = route_cost(final, table, priorities, use_priority)

        check_route(final, 5)
        assert cost_after <= cost_before


def test_duplicate_coordinates_are_both_visited():
    warehouse = {"latitude": 0.0, "longitude": 0.0}
    same_spot = {"latitude": 0.0, "longitude": 0.1}
    table = distance_table(warehouse, [same_spot, same_spot])
    priorities = [None, "LOW", "LOW"]

    first = nearest_neighbor_route(table, priorities, False)
    final = two_opt(first, table, priorities, False)

    check_route(final, 2)    # both deliveries appear exactly once
    assert route_distance(final, table) == pytest.approx(2 * calculate_distance(0, 0, 0, 0.1))


# ---------- API tests ----------

client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_database(monkeypatch):
    """Tests must not write to the real database, so we swap save_route
    for a fake one that always succeeds and returns row id 1."""
    def fake_save(stops, total_distance, use_priority):
        return 1

    monkeypatch.setattr("backend.main.save_route", fake_save)


def sample_request():
    """A valid request. Each test changes one piece of it."""
    return {
        "warehouse": {"name": "Main Warehouse", "latitude": 13.08, "longitude": 80.27},
        "deliveries": [
            {"name": "Shop A", "latitude": 13.12, "longitude": 80.20, "priority": "HIGH"},
            {"name": "Shop B", "latitude": 13.00, "longitude": 80.25, "priority": "LOW"},
            {"name": "Shop C", "latitude": 13.05, "longitude": 80.30, "priority": "MEDIUM"},
        ],
        "use_priority": False,
    }


def all_errors_as_text(response):
    """All error messages joined into one string, so tests can search in it."""
    return str(response.json()["detail"])


def test_optimize_without_priority():
    response = client.post("/optimize", json=sample_request())
    assert response.status_code == 200

    result = response.json()
    route = result["route"]
    delivery_numbers = [stop["number"] for stop in route[1:-1]]

    assert result["use_priority"] == False
    assert len(route) == 5
    assert route[0]["number"] == 0
    assert route[-1]["number"] == 0
    assert sorted(delivery_numbers) == [1, 2, 3]
    assert len(result["legs"]) == 4

    leg_sum = 0
    for leg in result["legs"]:
        leg_sum = leg_sum + leg["distance_km"]
    assert result["total_distance_km"] == pytest.approx(leg_sum, abs=0.05)


def test_optimize_with_priority_keeps_priority_in_result():
    data = sample_request()
    data["use_priority"] = True
    response = client.post("/optimize", json=data)

    assert response.status_code == 200
    result = response.json()
    assert result["use_priority"] == True
    assert result["route"][1]["priority"] in ["HIGH", "MEDIUM", "LOW"]


def test_zero_deliveries_are_rejected():
    data = sample_request()
    data["deliveries"] = []
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert "at least one delivery" in all_errors_as_text(response)


def test_eleven_deliveries_are_rejected():
    data = sample_request()
    data["deliveries"] = [data["deliveries"][0]] * 11
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert "maximum" in all_errors_as_text(response)


def test_ten_deliveries_are_accepted():
    data = sample_request()
    data["deliveries"] = []
    for i in range(10):
        data["deliveries"].append({
            "name": "Stop " + str(i + 1),
            "latitude": 13.0 + i * 0.01,
            "longitude": 80.2,
            "priority": "LOW",
        })
    response = client.post("/optimize", json=data)

    assert response.status_code == 200
    assert len(response.json()["route"]) == 12     # warehouse + 10 stops + warehouse


def test_bad_latitude_is_rejected():
    data = sample_request()
    data["deliveries"][0]["latitude"] = 95
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert "Delivery 1" in all_errors_as_text(response)
    assert "Latitude" in all_errors_as_text(response)


def test_missing_name_is_rejected():
    data = sample_request()
    data["deliveries"][1]["name"] = ""
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert "Delivery 2: name is missing" in all_errors_as_text(response)


def test_invalid_priority_is_rejected():
    data = sample_request()
    data["deliveries"][2]["priority"] = "URGENT"
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert "priority must be HIGH, MEDIUM or LOW" in all_errors_as_text(response)


def test_missing_warehouse_is_rejected():
    data = sample_request()
    del data["warehouse"]
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert "Warehouse is missing" in all_errors_as_text(response)


def test_duplicate_coordinates_stay_separate_stops():
    data = sample_request()
    same_spot = {"name": "Shop A", "latitude": 13.12, "longitude": 80.20, "priority": "LOW"}
    data["deliveries"] = [same_spot, dict(same_spot, name="Shop A copy")]
    response = client.post("/optimize", json=data)

    assert response.status_code == 200
    route = response.json()["route"]
    assert len(route) == 4
    assert sorted([route[1]["number"], route[2]["number"]]) == [1, 2]


def test_delivery_at_warehouse_location_is_accepted():
    data = sample_request()
    data["deliveries"] = [
        {"name": "Pickup", "latitude": 13.08, "longitude": 80.27, "priority": "HIGH"},
    ]
    response = client.post("/optimize", json=data)

    assert response.status_code == 200
    assert response.json()["total_distance_km"] == 0


def test_malformed_requests_are_rejected():
    data = sample_request()
    data["deliveries"] = "this is not a list"
    assert client.post("/optimize", json=data).status_code == 400

    # Not JSON at all: FastAPI itself answers 422.
    response = client.post("/optimize", content="this is not json",
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_all_errors_are_reported_together():
    data = sample_request()
    data["deliveries"][0]["latitude"] = 200
    data["deliveries"][1]["priority"] = "SOON"
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert len(response.json()["detail"]) >= 2


def test_single_delivery_route():
    data = sample_request()
    data["deliveries"] = [data["deliveries"][0]]
    response = client.post("/optimize", json=data)

    assert response.status_code == 200
    numbers = [stop["number"] for stop in response.json()["route"]]
    assert numbers == [0, 1, 0]


# ---------- Database saving tests ----------

def test_successful_route_is_reported_as_saved():
    response = client.post("/optimize", json=sample_request())

    assert response.status_code == 200
    result = response.json()
    assert result["saved"] == True
    assert result["route_id"] == 1


def test_route_is_still_returned_when_saving_fails(monkeypatch):
    def broken_save(stops, total_distance, use_priority):
        raise Exception("database is down")

    monkeypatch.setattr("backend.main.save_route", broken_save)
    response = client.post("/optimize", json=sample_request())

    assert response.status_code == 200
    result = response.json()
    assert result["saved"] == False
    assert "could not be saved" in result["save_error"]
    assert "route_id" not in result
    assert len(result["route"]) == 5      # the route is still there


def test_invalid_request_is_never_saved(monkeypatch):
    save_calls = []

    def recording_save(stops, total_distance, use_priority):
        save_calls.append(1)
        return 1

    monkeypatch.setattr("backend.main.save_route", recording_save)

    data = sample_request()
    data["deliveries"] = []
    response = client.post("/optimize", json=data)

    assert response.status_code == 400
    assert len(save_calls) == 0


def test_save_route_needs_database_url(monkeypatch):
    # This uses the real save_route (imported at the top), without a DATABASE_URL.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        save_route([{"name": "Main Warehouse"}], 10.0, False)
