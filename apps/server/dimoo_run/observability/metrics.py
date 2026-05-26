from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricsSnapshot:
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, list[float]] = field(default_factory=dict)


class MetricsRegistry:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def set_gauge(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        self.histograms.setdefault(name, []).append(value)

    def snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(
            counters=dict(self.counters),
            gauges=dict(self.gauges),
            histograms={key: list(value) for key, value in self.histograms.items()},
        )
