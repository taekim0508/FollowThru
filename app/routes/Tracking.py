from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import radians, sin, cos, sqrt, atan2
from typing import List, Optional, Dict, Any, Tuple


# ============================================================
# ENUMS
# ============================================================

class TrackingMethod(str, Enum):
    ATTENDANCE = "attendance"   # did they go there at all / how long were they there
    DURATION = "duration"       # did they stay there at least X seconds


class HabitPolarity(str, Enum):
    AFFIRMATIVE = "affirmative"   # being here supports the habit
    NEGATIVE = "negative"         # being here violates the habit


class EvaluationBucket(str, Enum):
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    INCONCLUSIVE = "inconclusive"


# ============================================================
# CORE DATA STRUCTURES
# ============================================================

@dataclass
class LocationPoint:
    timestamp: datetime
    latitude: float
    longitude: float
    accuracy_m: float = 20.0
    speed_mps: Optional[float] = None


@dataclass
class PointOfInterest:
    poi_id: str
    name: str
    latitude: float
    longitude: float
    radius_m: float
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HabitLocationRule:
    rule_id: str
    habit_name: str
    poi_ids: List[str]

    # "attendance" = presence at POI matters
    # "duration" = staying at POI for at least min_duration_seconds matters
    method: TrackingMethod

    # Whether matching this rule is good or bad for the habit
    polarity: HabitPolarity

    # Optional minimum dwell threshold.
    # For attendance, this can be None or used as a filter if desired.
    min_duration_seconds: Optional[int] = None

    # Optional min number of points inside POI to reduce GPS noise.
    min_points_inside: int = 1

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisitEvent:
    poi_id: str
    poi_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    points_inside: int
    rule_ids_matched: List[str] = field(default_factory=list)


@dataclass
class RuleEvaluation:
    rule_id: str
    habit_name: str
    bucket: EvaluationBucket
    matched: bool
    method: str
    polarity: str
    reason: str
    poi_matches: List[VisitEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# GEO HELPERS
# ============================================================

def haversine_distance_m(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    earth_radius_m = 6371000

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return earth_radius_m * c


def is_point_inside_poi(point: LocationPoint, poi: PointOfInterest) -> bool:
    distance = haversine_distance_m(
        point.latitude,
        point.longitude,
        poi.latitude,
        poi.longitude,
    )
    effective_radius = poi.radius_m + min(point.accuracy_m, 25)
    return distance <= effective_radius


# ============================================================
# VISIT / DWELL EXTRACTION
# ============================================================

def build_visits_for_poi(
    points: List[LocationPoint],
    poi: PointOfInterest,
    max_gap_seconds: int = 10 * 60,
) -> List[VisitEvent]:
    """
    Turns raw points into visit events for one POI.

    A visit starts when points begin falling inside the POI geofence.
    A visit ends when there is a gap or exit from the POI.
    """
    if not points:
        return []

    points = sorted(points, key=lambda p: p.timestamp)
    visits: List[VisitEvent] = []

    current_points: List[LocationPoint] = []

    def flush_visit(cluster: List[LocationPoint]) -> None:
        if not cluster:
            return
        visits.append(
            VisitEvent(
                poi_id=poi.poi_id,
                poi_name=poi.name,
                start_time=cluster[0].timestamp,
                end_time=cluster[-1].timestamp,
                duration_seconds=int(
                    (cluster[-1].timestamp - cluster[0].timestamp).total_seconds()
                ),
                points_inside=len(cluster),
            )
        )

    for point in points:
        inside = is_point_inside_poi(point, poi)

        if inside:
            if not current_points:
                current_points = [point]
            else:
                gap = (point.timestamp - current_points[-1].timestamp).total_seconds()
                if gap <= max_gap_seconds:
                    current_points.append(point)
                else:
                    flush_visit(current_points)
                    current_points = [point]
        else:
            if current_points:
                flush_visit(current_points)
                current_points = []

    if current_points:
        flush_visit(current_points)

    return visits


def build_all_visits(
    points: List[LocationPoint],
    pois: List[PointOfInterest],
    max_gap_seconds: int = 10 * 60,
) -> Dict[str, List[VisitEvent]]:
    """
    Returns:
        {
            poi_id: [VisitEvent, VisitEvent, ...]
        }
    """
    return {
        poi.poi_id: build_visits_for_poi(points, poi, max_gap_seconds=max_gap_seconds)
        for poi in pois
    }


# ============================================================
# RULE EVALUATION
# ============================================================

def evaluate_rule_against_visits(
    rule: HabitLocationRule,
    visits_by_poi: Dict[str, List[VisitEvent]],
) -> RuleEvaluation:
    matched_visits: List[VisitEvent] = []

    for poi_id in rule.poi_ids:
        poi_visits = visits_by_poi.get(poi_id, [])
        for visit in poi_visits:
            if visit.points_inside < rule.min_points_inside:
                continue

            if rule.method == TrackingMethod.ATTENDANCE:
                # Attendance means any visit counts unless a duration threshold is explicitly set.
                if (
                    rule.min_duration_seconds is None
                    or visit.duration_seconds >= rule.min_duration_seconds
                ):
                    matched_visits.append(visit)

            elif rule.method == TrackingMethod.DURATION:
                # Duration means the dwell threshold must be met.
                if (
                    rule.min_duration_seconds is not None
                    and visit.duration_seconds >= rule.min_duration_seconds
                ):
                    matched_visits.append(visit)

    matched = len(matched_visits) > 0

    if not matched:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            habit_name=rule.habit_name,
            bucket=EvaluationBucket.INCONCLUSIVE,
            matched=False,
            method=rule.method.value,
            polarity=rule.polarity.value,
            reason="No matching POI visit satisfied this rule.",
            poi_matches=[],
            metadata={"threshold_seconds": rule.min_duration_seconds},
        )

    bucket = (
        EvaluationBucket.AFFIRMATIVE
        if rule.polarity == HabitPolarity.AFFIRMATIVE
        else EvaluationBucket.NEGATIVE
    )

    matched_visits = sorted(
        matched_visits,
        key=lambda v: (v.duration_seconds, v.points_inside),
        reverse=True,
    )

    return RuleEvaluation(
        rule_id=rule.rule_id,
        habit_name=rule.habit_name,
        bucket=bucket,
        matched=True,
        method=rule.method.value,
        polarity=rule.polarity.value,
        reason=(
            f"Matched {len(matched_visits)} visit(s) for rule via method "
            f"'{rule.method.value}' with polarity '{rule.polarity.value}'."
        ),
        poi_matches=matched_visits,
        metadata={"threshold_seconds": rule.min_duration_seconds},
    )


def evaluate_rules(
    points: List[LocationPoint],
    pois: List[PointOfInterest],
    rules: List[HabitLocationRule],
    max_gap_seconds: int = 10 * 60,
) -> List[RuleEvaluation]:
    visits_by_poi = build_all_visits(
        points=points,
        pois=pois,
        max_gap_seconds=max_gap_seconds,
    )

    evaluations: List[RuleEvaluation] = []
    for rule in rules:
        evaluation = evaluate_rule_against_visits(rule, visits_by_poi)
        for visit in evaluation.poi_matches:
            visit.rule_ids_matched.append(rule.rule_id)
        evaluations.append(evaluation)

    return evaluations


# ============================================================
# HABIT-LEVEL AGGREGATION
# ============================================================

def aggregate_habit_results(
    evaluations: List[RuleEvaluation],
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregates multiple rules into one result per habit.

    Basic precedence:
      1. Any negative match => overall negative
      2. Else any affirmative match => overall affirmative
      3. Else inconclusive
    """
    by_habit: Dict[str, List[RuleEvaluation]] = {}

    for evaluation in evaluations:
        by_habit.setdefault(evaluation.habit_name, []).append(evaluation)

    output: Dict[str, Dict[str, Any]] = {}

    for habit_name, habit_evals in by_habit.items():
        negative_matches = [
            e for e in habit_evals
            if e.bucket == EvaluationBucket.NEGATIVE and e.matched
        ]
        affirmative_matches = [
            e for e in habit_evals
            if e.bucket == EvaluationBucket.AFFIRMATIVE and e.matched
        ]

        if negative_matches:
            overall = EvaluationBucket.NEGATIVE
            supporting = negative_matches
            reason = "At least one negative rule matched."
        elif affirmative_matches:
            overall = EvaluationBucket.AFFIRMATIVE
            supporting = affirmative_matches
            reason = "At least one affirmative rule matched and no negative rules matched."
        else:
            overall = EvaluationBucket.INCONCLUSIVE
            supporting = []
            reason = "No affirmative or negative rules matched."

        output[habit_name] = {
            "habit_name": habit_name,
            "bucket": overall.value,
            "reason": reason,
            "supporting_rules": supporting,
            "all_rules": habit_evals,
        }

    return output


# ============================================================
# EXAMPLE DATA
# ============================================================

EXAMPLE_POIS: List[PointOfInterest] = [
    PointOfInterest(
        poi_id="gym_1",
        name="Campus Gym",
        latitude=36.1447,
        longitude=-86.8027,
        radius_m=80,
        tags=["fitness", "affirmative_candidate"],
    ),
    PointOfInterest(
        poi_id="healthy_1",
        name="Sweetgreen",
        latitude=36.1512,
        longitude=-86.7985,
        radius_m=60,
        tags=["restaurant", "healthy_candidate"],
    ),
    PointOfInterest(
        poi_id="fastfood_1",
        name="McDonalds",
        latitude=36.1488,
        longitude=-86.7994,
        radius_m=70,
        tags=["restaurant", "negative_candidate"],
    ),
    PointOfInterest(
        poi_id="outside_1",
        name="Sidewalk Spot",
        latitude=36.1454,
        longitude=-86.8031,
        radius_m=25,
        tags=["outside", "linger_candidate"],
    ),
]

EXAMPLE_POINTS: List[LocationPoint] = [
    LocationPoint(datetime(2026, 3, 22, 8, 0, 0), 36.14535, -86.80310, 8, 0.2),
    LocationPoint(datetime(2026, 3, 22, 8, 3, 0), 36.14536, -86.80309, 8, 0.1),
    LocationPoint(datetime(2026, 3, 22, 8, 6, 0), 36.14534, -86.80312, 8, 0.0),
    LocationPoint(datetime(2026, 3, 22, 8, 10, 0), 36.14535, -86.80311, 8, 0.1),
    LocationPoint(datetime(2026, 3, 22, 8, 15, 0), 36.14536, -86.80310, 8, 0.0),

    LocationPoint(datetime(2026, 3, 22, 12, 5, 0), 36.15120, -86.79848, 12, 0.3),
    LocationPoint(datetime(2026, 3, 22, 12, 12, 0), 36.15119, -86.79850, 12, 0.1),

    LocationPoint(datetime(2026, 3, 22, 18, 2, 0), 36.14470, -86.80272, 10, 0.5),
    LocationPoint(datetime(2026, 3, 22, 18, 25, 0), 36.14469, -86.80273, 10, 0.2),
]

EXAMPLE_RULES: List[HabitLocationRule] = [
    # Attendance-based affirmative example
    HabitLocationRule(
        rule_id="rule_gym_attendance",
        habit_name="exercise_daily",
        poi_ids=["gym_1"],
        method=TrackingMethod.ATTENDANCE,
        polarity=HabitPolarity.AFFIRMATIVE,
        min_duration_seconds=None,
    ),

    # Attendance-based negative example
    HabitLocationRule(
        rule_id="rule_fastfood_attendance",
        habit_name="eat_clean",
        poi_ids=["fastfood_1"],
        method=TrackingMethod.ATTENDANCE,
        polarity=HabitPolarity.NEGATIVE,
        min_duration_seconds=None,
    ),

    # Attendance-based affirmative with a dwell filter
    HabitLocationRule(
        rule_id="rule_healthy_restaurant",
        habit_name="eat_clean",
        poi_ids=["healthy_1"],
        method=TrackingMethod.ATTENDANCE,
        polarity=HabitPolarity.AFFIRMATIVE,
        min_duration_seconds=5 * 60,
    ),

    # Duration-based negative example
    HabitLocationRule(
        rule_id="rule_linger_outside",
        habit_name="avoid_smoking",
        poi_ids=["outside_1"],
        method=TrackingMethod.DURATION,
        polarity=HabitPolarity.NEGATIVE,
        min_duration_seconds=15 * 60,
    ),
]


# ============================================================
# OPTIONAL HELPERS
# ============================================================

def summarize_visit_event(visit: VisitEvent) -> Dict[str, Any]:
    return {
        "poi_id": visit.poi_id,
        "poi_name": visit.poi_name,
        "start_time": visit.start_time.isoformat(),
        "end_time": visit.end_time.isoformat(),
        "duration_seconds": visit.duration_seconds,
        "points_inside": visit.points_inside,
        "rule_ids_matched": visit.rule_ids_matched,
    }


def serialize_rule_evaluation(evaluation: RuleEvaluation) -> Dict[str, Any]:
    return {
        "rule_id": evaluation.rule_id,
        "habit_name": evaluation.habit_name,
        "bucket": evaluation.bucket.value,
        "matched": evaluation.matched,
        "method": evaluation.method,
        "polarity": evaluation.polarity,
        "reason": evaluation.reason,
        "poi_matches": [summarize_visit_event(v) for v in evaluation.poi_matches],
        "metadata": evaluation.metadata,
    }


# ============================================================
# DEMO
# ============================================================

if __name__ == "__main__":
    evaluations = evaluate_rules(
        points=EXAMPLE_POINTS,
        pois=EXAMPLE_POIS,
        rules=EXAMPLE_RULES,
    )

    for e in evaluations:
        print(serialize_rule_evaluation(e))

    print("\nAGGREGATED:\n")
    aggregated = aggregate_habit_results(evaluations)
    for habit_name, result in aggregated.items():
        print(habit_name, "=>", result["bucket"], "|", result["reason"])