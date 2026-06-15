class MetricResultStore:
    def __init__(self) -> None:
        self._items = []

    def add_many(self, items):
        self._items.extend(items)
