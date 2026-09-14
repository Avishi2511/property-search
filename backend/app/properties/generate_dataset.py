"""Generates a synthetic-but-realistic Bangalore property dataset.

Run directly to (re)write app/properties/data/properties.json and
app/properties/data/landmarks.json:

    python -m app.properties.generate_dataset

The generator is seeded, so output is deterministic and diffable across runs.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from app.properties.localities import LOCALITIES

DATA_DIR = Path(__file__).parent / "data"
SEED = 42
NUM_PROPERTIES = 550

BUILDERS = [
    "Skyline Builders", "Urban Nest Developers", "GreenArch Homes",
    "Metro Crest Realty", "Silver Oak Constructions", "Palm Grove Developers",
    "Horizon Living", "BlueStone Habitat", "Crimson Peak Builders",
    "Everest Urban Homes", "Zenith Realty", "Maple Ridge Developers",
    "Orchid Spaces", "Granite Hills Builders", "Cascade Homes",
]

PROJECT_WORDS_1 = ["Example", "Sunrise", "Silver", "Palm", "Emerald", "Royal",
                   "Maple", "Crystal", "Golden", "Orchid", "Cedar", "Willow",
                   "Amber", "Ivory", "Coral"]
PROJECT_WORDS_2 = ["Heights", "Residency", "Meadows", "Enclave", "Gardens",
                   "Towers", "Court", "Greens", "Woods", "Vista", "Pearl",
                   "Grove", "Square", "Estate", "Springs"]

AMENITY_POOL = [
    "pool", "gym", "park", "clubhouse", "security", "power_backup", "lift",
    "children_play_area", "jogging_track", "indoor_games", "tennis_court",
    "badminton_court", "yoga_deck", "co_working_space", "amphitheater",
    "pet_park", "parking",
]

# Named landmarks used by find_nearby_places(); a handful per locality area,
# roughly geographically placed (not real addresses, illustrative for the demo).
LANDMARK_TEMPLATES = [
    ("hospital", "{loc} General Hospital"),
    ("hospital", "{loc} Multispecialty Hospital"),
    ("school", "{loc} Public School"),
    ("metro", "{loc} Metro Station"),
    ("office_hub", "{loc} Tech Park"),
    ("mall", "{loc} Central Mall"),
]


def _jitter(lat: float, lng: float, rng: random.Random, spread: float = 0.02) -> tuple[float, float]:
    return (
        round(lat + rng.uniform(-spread, spread), 6),
        round(lng + rng.uniform(-spread, spread), 6),
    )


_BASE_YEAR, _BASE_MONTH = 2026, 9  # roughly "today" for this dataset


def _possession_date(rng: random.Random) -> str:
    # Spread possession dates from "ready to move" (a few months ago) out to
    # ~4 years in the future, relative to the base date above.
    months_offset = rng.randint(-6, 48)
    total_months = (_BASE_YEAR * 12 + (_BASE_MONTH - 1)) + months_offset
    year, month0 = divmod(total_months, 12)
    return f"{year:04d}-{month0 + 1:02d}"


def _tier_distance_bounds(tier: str) -> tuple[float, float]:
    # Premium/high-tier localities tend to have closer amenities.
    return {
        "premium": (0.3, 3.0),
        "high": (0.5, 4.0),
        "mid": (0.8, 6.0),
        "value": (1.5, 9.0),
    }[tier]


def generate_properties(n: int, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    properties = []
    for i in range(1, n + 1):
        loc_name, base_lat, base_lng, ppsf_base, tier = rng.choice(LOCALITIES)
        lat, lng = _jitter(base_lat, base_lng, rng)

        bedrooms = rng.choices([1, 2, 3, 4], weights=[10, 35, 40, 15])[0]
        area_sqft = {
            1: rng.randint(500, 750),
            2: rng.randint(850, 1250),
            3: rng.randint(1300, 1900),
            4: rng.randint(1900, 2800),
        }[bedrooms]

        ppsf = max(3000, int(rng.gauss(ppsf_base, ppsf_base * 0.12)))
        price = int(round(ppsf * area_sqft, -4))  # round to nearest 10k

        builder = rng.choice(BUILDERS)
        project = f"{rng.choice(PROJECT_WORDS_1)} {rng.choice(PROJECT_WORDS_2)}"

        num_amenities = rng.randint(3, len(AMENITY_POOL))
        amenities = sorted(rng.sample(AMENITY_POOL, num_amenities))

        low, high = _tier_distance_bounds(tier)
        nearby = {
            "hospital": round(rng.uniform(low, high), 1),
            "school": round(rng.uniform(low * 0.8, high * 0.8), 1),
            "metro": round(rng.uniform(low, high * 1.3), 1),
        }

        properties.append({
            "id": f"property_{i:03d}",
            "project": project,
            "location": loc_name,
            "city": "Bangalore",
            "latitude": lat,
            "longitude": lng,
            "price": price,
            "bedrooms": bedrooms,
            "area_sqft": area_sqft,
            "possession": _possession_date(rng),
            "builder": builder,
            "amenities": amenities,
            "nearby": nearby,
        })
    return properties


def generate_landmarks(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed + 1)
    landmarks = []
    idx = 1
    for loc_name, base_lat, base_lng, _, _ in LOCALITIES:
        for category, template in LANDMARK_TEMPLATES:
            lat, lng = _jitter(base_lat, base_lng, rng, spread=0.015)
            landmarks.append({
                "id": f"landmark_{idx:03d}",
                "name": template.format(loc=loc_name),
                "category": category,
                "location": loc_name,
                "latitude": lat,
                "longitude": lng,
            })
            idx += 1
    return landmarks


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    properties = generate_properties(NUM_PROPERTIES)
    (DATA_DIR / "properties.json").write_text(
        json.dumps(properties, indent=2), encoding="utf-8"
    )

    landmarks = generate_landmarks()
    (DATA_DIR / "landmarks.json").write_text(
        json.dumps(landmarks, indent=2), encoding="utf-8"
    )

    print(f"Wrote {len(properties)} properties and {len(landmarks)} landmarks to {DATA_DIR}")


if __name__ == "__main__":
    main()
