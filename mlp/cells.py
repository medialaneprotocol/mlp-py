"""The repair-cell grid and the per-receiver convergence accounting."""


class CellGrid:
    def __init__(self, width, height, cell_size):
        self.width = width
        self.height = height
        self.cell_size = cell_size

    def cols(self):
        return (self.width + self.cell_size - 1) // self.cell_size

    def rows(self):
        return (self.height + self.cell_size - 1) // self.cell_size

    def cells(self):
        return self.cols() * self.rows()


class CellAccounting:
    """A cell is pending from the moment an update covering it is sent
    until the receiver applies it."""

    def __init__(self, grid):
        self.grid = grid
        self.pending = set()
        self.applied = set()

    def mark_pending(self, cells):
        for c in cells:
            self.pending.add(c)
            self.applied.discard(c)

    def mark_applied(self, cells):
        for c in cells:
            self.pending.discard(c)
            self.applied.add(c)

    def pending_count(self):
        return len(self.pending)

    def converged(self):
        return not self.pending
