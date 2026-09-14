"""Canonical list of Bangalore localities used by the dataset generator and by
constraint extraction (matching a buyer's spoken locality against real names).

Each entry: (name, lat, lng, price_per_sqft_base, tier).
"""

LOCALITIES: list[tuple[str, float, float, int, str]] = [
    ("Koramangala", 12.9352, 77.6245, 13500, "premium"),
    ("Indiranagar", 12.9719, 77.6412, 13000, "premium"),
    ("HSR Layout", 12.9121, 77.6446, 10500, "high"),
    ("Whitefield", 12.9698, 77.7500, 7200, "mid"),
    ("Marathahalli", 12.9569, 77.7011, 7800, "mid"),
    ("Electronic City", 12.8452, 77.6602, 5600, "value"),
    ("Sarjapur Road", 12.9010, 77.6874, 7000, "mid"),
    ("JP Nagar", 12.9077, 77.5906, 8600, "high"),
    ("Jayanagar", 12.9308, 77.5838, 11000, "premium"),
    ("Hebbal", 13.0358, 77.5970, 8200, "high"),
    ("Yelahanka", 13.1007, 77.5963, 6100, "value"),
    ("Bannerghatta Road", 12.8845, 77.5975, 7300, "mid"),
    ("Bellandur", 12.9257, 77.6784, 8900, "high"),
    ("Hennur", 13.0359, 77.6389, 6700, "mid"),
    ("Rajajinagar", 12.9915, 77.5526, 9800, "high"),
    ("Malleswaram", 13.0035, 77.5709, 12200, "premium"),
    ("Kanakapura Road", 12.8697, 77.5445, 5900, "value"),
    ("Devanahalli", 13.2437, 77.7139, 4800, "value"),
]

LOCALITY_NAMES: list[str] = [name for name, *_ in LOCALITIES]

# Lookup by lowercase name -> (lat, lng), so extraction can resolve "koramangala"
# to coordinates without depending on the property dataset itself.
LOCALITY_COORDS: dict[str, tuple[float, float]] = {
    name.lower(): (lat, lng) for name, lat, lng, _, _ in LOCALITIES
}
