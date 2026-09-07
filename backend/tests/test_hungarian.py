import random
from itertools import permutations

from app.services.hungarian import solve_assignment, solve_rectangular_assignment


def brute_force_rectangular(cost_matrix: list[list[float]]) -> float:
    rows = len(cost_matrix)
    cols = len(cost_matrix[0])
    k = min(rows, cols)
    best = float("inf")
    for cols_subset in permutations(range(cols), k):
        for rows_subset in permutations(range(rows), k):
            cost = sum(cost_matrix[r][c] for r, c in zip(rows_subset, cols_subset))
            best = min(best, cost)
    return best


def test_square_matrix_matches_known_optimum() -> None:
    # Classic textbook example: optimal assignment costs 5+3+4 = ... verify via brute force too.
    matrix = [
        [4, 1, 3],
        [2, 0, 5],
        [3, 2, 2],
    ]
    row_to_col, total_cost = solve_assignment(matrix)
    assert len(set(row_to_col)) == 3
    assert total_cost == brute_force_rectangular(matrix)


def test_matches_brute_force_on_random_rectangular_matrices() -> None:
    random.seed(7)
    for _ in range(100):
        rows = random.randint(1, 6)
        cols = random.randint(1, 6)
        matrix = [[round(random.uniform(0, 25), 2) for _ in range(cols)] for _ in range(rows)]

        _, total_cost = solve_rectangular_assignment(matrix)
        assert abs(total_cost - brute_force_rectangular(matrix)) < 1e-6


def test_rectangular_assignment_drops_infeasible_pairs() -> None:
    from app.services.hungarian import INFEASIBLE_COST

    matrix = [
        [1.0, INFEASIBLE_COST],
        [INFEASIBLE_COST, 1.0],
        [5.0, 5.0],
    ]
    pairs, total_cost = solve_rectangular_assignment(matrix)
    assert (0, 0) in pairs
    assert (1, 1) in pairs
    assert total_cost == 2.0


def test_empty_inputs_return_no_assignment() -> None:
    assert solve_assignment([]) == ([], 0.0)
    assert solve_rectangular_assignment([]) == ([], 0.0)
