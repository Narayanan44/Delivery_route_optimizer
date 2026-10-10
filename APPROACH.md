# Approach

This document explains how I thought about the problem, how the algorithm works,
and why I made each choice. Where something is a judgement call and not a proven
fact, I have tried to say so.

## 1. The problem

Given a warehouse and up to 10 delivery stops, find a good order to visit them.

- The trip starts at the warehouse and returns to the same warehouse.
- Every delivery is visited exactly once.
- Every delivery has a priority: HIGH, MEDIUM or LOW.
- There are two modes. Without Priority should give a short trip. With Priority
  should reach important deliveries earlier.

This is a small version of the travelling salesman problem, with a priority twist.

## 2. Overview of the pipeline

Every request goes through the same steps:

1. Check the input and collect every problem (nothing invalid goes further).
2. Build a distance table between all places (Haversine).
3. Build a first route with Nearest Neighbour.
4. Improve it with 2-Opt, judged by the cost of the chosen mode.
5. Turn the route into the answer (stops, legs, total) and try to save it.

## 3. Distance: Haversine and the distance table

**Haversine.** The Earth is a sphere, so flat x/y distance on latitude and
longitude would be wrong. Haversine gives the straight-line distance over the
surface between two points. I used an Earth radius of 6371.0088 km.

This is *not* road distance. A real road distance needs a routing service, which
the assignment did not ask for, so the interface says clearly that the numbers are
straight-line distances.

**Small safety detail.** Because of floating-point rounding, the value inside the
formula can come out slightly above 1, and the `asin` step would crash. I cap it
at 1.

**Distance table.** I calculate the distance between every pair of places once and
store it in a table. Place 0 is the warehouse and places 1 to n are the
deliveries, in the order the user entered them. After that, the algorithm only
looks numbers up. This keeps the algorithm simple and fast: for 11 places it is
121 small calculations, done once.

**Why index by position and not by coordinates.** Two different deliveries can
have exactly the same coordinates, and a delivery can be at the warehouse itself.
Because every stop has its own index, they stay separate stops. Nothing can be
merged, skipped or visited twice by accident.

## 4. The cost: what "a good route" means

Both algorithms need one number that says how bad a route is (lower is better).
This is the most important design decision, because 2-Opt always optimises exactly
this number.

**Without Priority**

```
cost = total distance of the route
```

**With Priority**

```
cost = total distance + delay penalty

delay penalty = sum over all deliveries of ( weight of the delivery
                                             x km travelled before reaching it )
```

Weights: **HIGH = 4, MEDIUM = 2, LOW = 1.**

**Why this shape.** A delivery that is reached late should cost more, and a
more important delivery should cost more when late. Multiplying the weight by the
distance already travelled does both. Adding the real total distance keeps the
route from becoming silly: the algorithm cannot ignore distance completely just to
push a HIGH stop to the front.

**Why 4, 2, 1.** Each level is twice as important as the one below it, so a HIGH
delivery reached late hurts four times as much as a LOW one reached late. This is
a judgement call. I cannot prove these are the right numbers, and a real business
would tune them. They live in one place (`Priority_Weight`) so they are easy to
change.

**Why "km travelled so far" is the delay.** There is no speed or time data in the
input. Distance travelled before arrival is the closest stand-in for how long a
customer waits.

**A worked example (checked by a test).** Distances: warehouse to stop 1 is 10 km,
warehouse to stop 2 is 20 km, stop 1 to stop 2 is 10 km. Stop 1 is HIGH, stop 2 is
LOW.

- Route 0, 1, 2, 0: distance 40. Stop 1 is reached after 10 km (4 x 10 = 40), stop
  2 after 20 km (1 x 20 = 20). Cost = 40 + 40 + 20 = **100**.
- Route 0, 2, 1, 0: distance 40. Stop 2 is reached after 20 km (1 x 20 = 20), stop
  1 after 30 km (4 x 30 = 120). Cost = 40 + 20 + 120 = **180**.

Both routes are 40 km long, but visiting the HIGH stop first is much cheaper
under this cost, so priority mode prefers it.

## 5. Nearest Neighbour: the first route

Start at the warehouse. Look at the deliveries not visited yet, go to the best one,
repeat until none are left, then return to the warehouse.

- **Without Priority**, "best" means the closest.
- **With Priority**, "best" means the smallest *distance divided by the weight*.
  Dividing by the weight makes an important stop look closer than it really is, so
  it tends to be picked earlier. For example a HIGH stop 15 km away scores 3.75,
  and beats a LOW stop 10 km away that scores 10.

**Ties.** If two stops score the same, the one entered first wins. This makes the
result repeatable: the same input always gives the same route.

**Weakness.** Nearest Neighbour is greedy. An early "closest" choice can force a
long jump at the end. It is only a starting point, which is why the next step
exists. In priority mode the division trick is also just a rule of thumb, it does
not directly minimise the real cost.

## 6. 2-Opt: improving the route

2-Opt takes a part of the route, reverses it, and checks the cost:

```
route:      W  A  B  C  D  E  W
reverse B..D:
new route:  W  A  D  C  B  E  W
```

If the new route has a lower cost, I keep it. I repeat over every possible part
until a whole pass finds no improvement.

**It judges the real cost of the selected mode.** After each reversal I recompute
the full cost of the new route. This matters in priority mode: reversing a part of
the route changes when every stop inside it is reached, not only the total
distance, so the penalty has to be recalculated. Using the right cost in each mode
is also what makes 2-Opt meaningful for priority (a test checks that it moves a HIGH
stop to the front).

**It always finishes.** A change is kept only if the cost goes strictly down. The
cost cannot go down forever and there is a limited number of possible routes, so
the loop must stop. It cannot swap back and forth.

**The warehouse stays put.** The loops only touch positions between the first and
last place, so the route always starts and ends at the warehouse.

**Cost of the algorithm.** One pass tries about n squared reversals and each
costs about n to evaluate, so roughly n cubed per pass. For at most 10 stops this
is tiny.

## 7. No guarantee of the best route

Nearest Neighbour plus 2-Opt is a heuristic. 2-Opt stops at a "local optimum": a
route where no single reversal helps, which may still not be the best route
overall. I do not claim the result is optimal.

With at most 10 deliveries, trying every order would also be possible (9 factorial
is 362,880 orders). I did not do that because the assignment asked for Nearest
Neighbour and 2-Opt. If I had more time, I would use brute force on small inputs as
a way to measure how close the heuristic gets.

## 8. Input rules and why

| Case | What happens | Why |
|---|---|---|
| 0 deliveries | Rejected | Nothing to optimise, and it usually means the user forgot to add stops |
| 1 delivery | Accepted | A valid trip: warehouse, stop, warehouse |
| 10 deliveries | Accepted | This is the limit |
| More than 10 | Rejected | Over the limit, and the message says so |
| Missing or invalid latitude/longitude | Rejected | The message names the delivery and the problem |
| Latitude outside -90 to 90, longitude outside -180 to 180 | Rejected | Not real coordinates |
| "nan" or "inf" as a coordinate | Rejected | They look like numbers but are not valid positions |
| Missing name | Rejected | Names label the stops in the result and the diagram |
| Unknown priority | Rejected | Must be HIGH, MEDIUM or LOW, even in Without Priority mode, so the data is always clean |
| Two deliveries at the same coordinates | Accepted | They are different deliveries, so both stay as separate stops |
| A delivery at the warehouse location | Accepted | A real situation (for example a pickup), the distance is 0 |
| Broken JSON or the wrong shape | Rejected | One clear error instead of a crash |

All problems are collected and sent back together, so the user can fix them in one
go. Nothing invalid is silently ignored or corrected.

## 9. Database and failure handling

Every successful result is saved in one table, `routes`, with these columns: id,
route (as text), total_distance, priority_used and created_at. The database address
comes from the `DATABASE_URL` environment variable, and the `.env` file is never
committed. The table is created automatically on the first save.

**If saving fails, the route is still returned.** The calculation does not depend
on the database, so a database problem should not throw away a good answer. The
response says `saved: false` with a plain message, and the page shows it. It never
claims something was saved when it was not. The real database error only goes to the
server log, so internal details are not shown to the user. Invalid requests are
never saved.

## 10. Testing

There are 46 pytest tests. They check:

- the distance values and the distance table (shape, symmetry, zeros, duplicates)
- that every route starts and ends at the warehouse and visits each delivery once
- the cost calculation, with the hand-worked example above
- that Nearest Neighbour prefers a HIGH stop in priority mode
- that 2-Opt never makes the cost worse, fixes a bad route, and improves the
  priority cost
- all the input rules in the table above, including the 10 and 11 delivery limits
- what happens when saving fails

The API tests replace `save_route` with a fake, so they never write to a real
database. Saving to PostgreSQL I checked by hand.

## 11. Limitations and what I would improve

- Distances are straight lines, not roads. Real road distances would need a routing
  service.
- The result is a heuristic, not a proven best route.
- The weights 4, 2, 1 are my own choice. Letting the user set them would be better.
- "Km travelled" stands in for waiting time because there is no time data.
- Coordinates are only checked to be in range, not whether they are on land.
- I would add a comparison against trying every order for small inputs, and tests
  against a real test database.