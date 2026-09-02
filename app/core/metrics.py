import threading
from collections import defaultdict
from collections.abc import Sequence


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class Counter:
    def __init__(
        self, name: str, description: str, label_names: Sequence[str] = ()
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self._values: dict[tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, value: float = 1.0, **labels: str) -> None:
        key = tuple(str(labels.get(lbl, "")) for lbl in self.label_names)
        with self._lock:
            self._values[key] += value

    def render(self) -> str:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            items = sorted(self._values.items())
        if not items and not self.label_names:
            lines.append(f"{self.name} 0.0")
        for key, val in items:
            if self.label_names:
                lbls = ",".join(
                    f'{lbl}="{_escape_label_value(key[i])}"'
                    for i, lbl in enumerate(self.label_names)
                )
                lines.append(f"{self.name}{{{lbls}}} {val}")
            else:
                lines.append(f"{self.name} {val}")
        return "\n".join(lines)


class Histogram:
    DEFAULT_BUCKETS = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
        60.0,
    )

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_BUCKETS,
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self.buckets = tuple(sorted(buckets))
        self._counts: dict[tuple[str, ...], float] = defaultdict(float)
        self._sums: dict[tuple[str, ...], float] = defaultdict(float)
        self._bucket_counts: dict[tuple[tuple[str, ...], float], float] = defaultdict(
            float
        )
        self._lock = threading.Lock()

    def observe(self, value: float, **labels: str) -> None:
        key = tuple(str(labels.get(lbl, "")) for lbl in self.label_names)
        with self._lock:
            self._counts[key] += 1
            self._sums[key] += value
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[(key, bucket)] += 1

    def render(self) -> str:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            keys = sorted(self._counts.keys())
            counts = dict(self._counts)
            sums = dict(self._sums)
            bucket_counts = dict(self._bucket_counts)

        for key in keys:
            lbl_pairs = [
                f'{lbl}="{_escape_label_value(key[i])}"'
                for i, lbl in enumerate(self.label_names)
            ]
            for bucket in self.buckets:
                count = bucket_counts.get((key, bucket), 0.0)
                lbls = ",".join(lbl_pairs + [f'le="{bucket}"'])
                lines.append(f"{self.name}_bucket{{{lbls}}} {count}")
            inf_lbls = ",".join(lbl_pairs + ['le="+Inf"'])
            total_count = counts.get(key, 0.0)
            lines.append(f"{self.name}_bucket{{{inf_lbls}}} {total_count}")
            base_lbls = f"{{{','.join(lbl_pairs)}}}" if lbl_pairs else ""
            lines.append(f"{self.name}_sum{base_lbls} {sums.get(key, 0.0):.4f}")
            lines.append(f"{self.name}_count{base_lbls} {total_count}")

        return "\n".join(lines)


class MetricsRegistry:
    def __init__(self) -> None:
        self.http_requests_total = Counter(
            name="rag_http_requests_total",
            description="Total HTTP requests processed by the API",
            label_names=("method", "path", "status_code"),
        )
        self.http_request_duration_seconds = Histogram(
            name="rag_http_request_duration_seconds",
            description="HTTP request latency in seconds",
            label_names=("method", "path"),
        )
        self.search_duration_seconds = Histogram(
            name="rag_search_duration_seconds",
            description="Duration of semantic search queries in seconds",
        )
        self.llm_duration_seconds = Histogram(
            name="rag_llm_duration_seconds",
            description="Duration of LLM calls in seconds",
            label_names=("operation",),
        )
        self.document_indexing_duration_seconds = Histogram(
            name="rag_document_indexing_duration_seconds",
            description="Duration of document ingestion and indexing in seconds",
            label_names=("outcome",),
        )
        self.document_jobs_total = Counter(
            name="rag_document_jobs_total",
            description="Total background document indexing jobs",
            label_names=("outcome",),
        )

    def render(self) -> str:
        sections = [
            self.http_requests_total.render(),
            self.http_request_duration_seconds.render(),
            self.search_duration_seconds.render(),
            self.llm_duration_seconds.render(),
            self.document_indexing_duration_seconds.render(),
            self.document_jobs_total.render(),
        ]
        return "\n\n".join(sections) + "\n"


metrics = MetricsRegistry()
