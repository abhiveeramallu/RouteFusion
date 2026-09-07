from __future__ import annotations

INFEASIBLE_COST = 1e9


def solve_assignment(cost_matrix: list[list[float]]) -> tuple[list[int], float]:
    """Kuhn-Munkres (Hungarian) algorithm, O(n^3), minimizing total cost.

    cost_matrix must be square. Non-square problems are padded by the caller
    with INFEASIBLE_COST edges so unmatched rows/columns land on dummy slots.
    Returns (row_to_col, total_cost) where row_to_col[i] is the column
    assigned to row i.
    """
    n = len(cost_matrix)
    if n == 0:
        return [], 0.0
    for row in cost_matrix:
        if len(row) != n:
            raise ValueError("cost_matrix must be square")

    # 1-indexed potentials/tracking arrays, standard Jonker-Volgenant-style
    # shortest augmenting path implementation of Kuhn-Munkres.
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)  # p[j] = row currently matched to column j (1-indexed columns)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = -1
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j

            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta

            j0 = j1
            if p[j0] == 0:
                break

        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1

    row_to_col = [0] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            row_to_col[p[j] - 1] = j - 1

    total_cost = sum(cost_matrix[i][row_to_col[i]] for i in range(n))
    return row_to_col, total_cost


def solve_rectangular_assignment(
    cost_matrix: list[list[float]],
) -> tuple[list[tuple[int, int]], float]:
    """Solves a possibly non-square assignment problem by padding with
    INFEASIBLE_COST dummy edges, then dropping pairs that landed on a dummy
    or an already-infeasible real edge. Returns (matched_pairs, total_cost)
    where matched_pairs is a list of (row_index, col_index).
    """
    rows = len(cost_matrix)
    cols = len(cost_matrix[0]) if rows else 0
    if rows == 0 or cols == 0:
        return [], 0.0

    n = max(rows, cols)
    padded = [
        [
            cost_matrix[i][j] if i < rows and j < cols else INFEASIBLE_COST
            for j in range(n)
        ]
        for i in range(n)
    ]

    row_to_col, _ = solve_assignment(padded)

    matched: list[tuple[int, int]] = []
    total_cost = 0.0
    for i in range(rows):
        j = row_to_col[i]
        if j < cols and cost_matrix[i][j] < INFEASIBLE_COST:
            matched.append((i, j))
            total_cost += cost_matrix[i][j]

    return matched, total_cost
