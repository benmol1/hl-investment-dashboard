"""Load and validate the semantic layer definitions.

Parses definitions.yml into frozen dataclasses once at first use and fails
fast (at import of the bot, in practice) if the layer is malformed. All SQL
fragments here are trusted, hand-curated strings from the YAML file — the
compiler never accepts identifiers or expressions from the LLM.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

DEFINITIONS_PATH = Path(__file__).parent / "definitions.yml"

VALID_AGGS = {"sum", "avg", "min", "max", "count", "count_distinct", "last"}
VALID_ADDITIVITY = {"additive", "semi"}

# MEASURE(name) references inside derived metric expressions
_MEASURE_REF = re.compile(r"MEASURE\(\s*(\w+)\s*\)")


class SemanticLayerError(Exception):
    """The definitions file itself is invalid."""


@dataclass(frozen=True)
class Join:
    table: str
    alias: str
    on: str


@dataclass(frozen=True)
class Dimension:
    name: str
    expr: str
    description: str = ""
    type: str = "categorical"  # categorical | time
    values: tuple[str, ...] = ()
    values_query: str | None = None

    @property
    def is_time(self) -> bool:
        return self.type == "time"


@dataclass(frozen=True)
class Measure:
    name: str
    agg: str
    expr: str
    description: str = ""
    additivity: str = "additive"
    filter: str | None = None


@dataclass(frozen=True)
class DerivedMetric:
    name: str
    expr: str
    description: str = ""

    @property
    def required_measures(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_MEASURE_REF.findall(self.expr)))


@dataclass(frozen=True)
class SemanticModel:
    name: str
    table: str
    description: str
    joins: tuple[Join, ...] = ()
    dimensions: tuple[Dimension, ...] = ()
    measures: tuple[Measure, ...] = ()
    metrics: tuple[DerivedMetric, ...] = ()
    primary_time_dimension: str | None = None

    def dimension(self, name: str) -> Dimension | None:
        return next((d for d in self.dimensions if d.name == name), None)

    def measure(self, name: str) -> Measure | None:
        return next((m for m in self.measures if m.name == name), None)

    def metric(self, name: str) -> DerivedMetric | None:
        return next((m for m in self.metrics if m.name == name), None)

    @property
    def time_dimension(self) -> Dimension | None:
        if self.primary_time_dimension:
            return self.dimension(self.primary_time_dimension)
        return None

    @property
    def metric_names(self) -> list[str]:
        return [m.name for m in self.measures] + [m.name for m in self.metrics]


def _parse_model(raw: dict) -> SemanticModel:
    name = raw["name"]
    joins = tuple(Join(j["table"], j["alias"], j["sql_on"]) for j in raw.get("joins") or ())
    dimensions = tuple(
        Dimension(
            name=d["name"],
            expr=d["expr"],
            description=d.get("description", ""),
            type=d.get("type", "categorical"),
            values=tuple(d.get("values") or ()),
            values_query=d.get("values_query"),
        )
        for d in raw.get("dimensions") or ()
    )
    measures = tuple(
        Measure(
            name=m["name"],
            agg=m["agg"],
            expr=m["expr"],
            description=m.get("description", ""),
            additivity=m.get("additivity", "additive"),
            filter=m.get("filter"),
        )
        for m in raw.get("measures") or ()
    )
    metrics = tuple(
        DerivedMetric(name=m["name"], expr=m["expr"], description=m.get("description", ""))
        for m in raw.get("metrics") or ()
    )
    return SemanticModel(
        name=name,
        table=raw["table"],
        description=raw.get("description", ""),
        joins=joins,
        dimensions=dimensions,
        measures=measures,
        metrics=metrics,
        primary_time_dimension=raw.get("primary_time_dimension"),
    )


def _validate_model(model: SemanticModel) -> None:
    def fail(msg: str) -> None:
        raise SemanticLayerError(f"semantic model '{model.name}': {msg}")

    names = [d.name for d in model.dimensions] + model.metric_names
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        fail(f"duplicate field names {sorted(dupes)}")

    aliases = {"base"} | {j.alias for j in model.joins}
    if len(aliases) != len(model.joins) + 1:
        fail("duplicate join aliases (or a join aliased 'base')")

    for m in model.measures:
        if m.agg not in VALID_AGGS:
            fail(f"measure '{m.name}' has unknown agg '{m.agg}'")
        if m.additivity not in VALID_ADDITIVITY:
            fail(f"measure '{m.name}' has unknown additivity '{m.additivity}'")
        if m.agg == "last" and model.time_dimension is None:
            fail(f"measure '{m.name}' uses agg 'last' but the model has no primary time dimension")
    if model.primary_time_dimension:
        td = model.dimension(model.primary_time_dimension)
        if td is None or not td.is_time:
            fail(f"primary_time_dimension '{model.primary_time_dimension}' is not a time dimension")
    if any(m.additivity == "semi" for m in model.measures) and model.time_dimension is None:
        fail("has semi-additive measures but no primary time dimension")

    measure_names = {m.name for m in model.measures}
    for dm in model.metrics:
        missing = set(dm.required_measures) - measure_names
        if missing:
            fail(f"derived metric '{dm.name}' references unknown measures {sorted(missing)}")
        if not dm.required_measures:
            fail(f"derived metric '{dm.name}' references no MEASURE(...) at all")


@dataclass(frozen=True)
class Registry:
    models: tuple[SemanticModel, ...]

    def model(self, name: str) -> SemanticModel | None:
        return next((m for m in self.models if m.name == name), None)

    @property
    def model_names(self) -> list[str]:
        return [m.name for m in self.models]


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    raw = yaml.safe_load(DEFINITIONS_PATH.read_text(encoding="utf-8"))
    models = tuple(_parse_model(m) for m in raw["semantic_models"])
    if len({m.name for m in models}) != len(models):
        raise SemanticLayerError("duplicate semantic model names")
    for model in models:
        _validate_model(model)
    return Registry(models=models)
