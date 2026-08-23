from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MASS_UNITS_IN_GRAMS = {
    "g": Decimal("1"),
    "oz": Decimal("28.349523125"),
}

VOLUME_UNITS_IN_MILLILITERS = {
    "ml": Decimal("1"),
    "fl_oz": Decimal("29.5735295625"),
    "cup": Decimal("236.5882365"),
    "tbsp": Decimal("14.78676478125"),
    "tsp": Decimal("4.92892159375"),
}

UNIT_LABELS = {
    "g": "g",
    "ml": "ml",
    "oz": "oz",
    "fl_oz": "fl oz",
    "cup": "cup",
    "tbsp": "tbsp",
    "tsp": "tsp",
    "item": "item",
    "serving": "serving",
}

UNIT_OPTION_LABELS = {
    "g": "g",
    "ml": "ml",
    "oz": "oz",
    "fl_oz": "fl oz",
    "cup": "cup",
    "tbsp": "tbsp",
    "tsp": "tsp",
}


def _decimal(value, *, default="1"):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)
    return parsed if parsed.is_finite() and parsed > 0 else Decimal(default)


def _decimal_string(value):
    return format(value.normalize(), "f")


def _clean_estimated_weight(value):
    weight = _decimal(value)
    quantum = Decimal("1") if weight >= 1 else Decimal("0.1")
    return weight.quantize(quantum, rounding=ROUND_HALF_UP)


def _clean_estimated_volume(value):
    volume = _decimal(value)
    fluid_ounces = volume / VOLUME_UNITS_IN_MILLILITERS["fl_oz"]
    quantum = Decimal("0.5") if fluid_ounces >= 1 else Decimal("0.25")
    clean_fluid_ounces = (fluid_ounces / quantum).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ) * quantum
    if clean_fluid_ounces <= 0:
        clean_fluid_ounces = quantum
    return clean_fluid_ounces * VOLUME_UNITS_IN_MILLILITERS["fl_oz"]


def portion_options_for_serving(
    *, quantity, unit, label="", weight_grams=None, volume_milliliters=None
):
    """Return exact display-unit conversions anchored to one declared serving."""

    base_quantity = _decimal(quantity)
    base_label = (
        str(label).strip()
        or f"{_decimal_string(base_quantity)} {UNIT_LABELS.get(unit, unit)}"
    )
    options = [
        {
            "key": "base",
            "label": base_label,
            "unit_label": "serving",
            "serving_multiplier": "1",
        }
    ]

    if unit not in MASS_UNITS_IN_GRAMS and weight_grams is not None:
        serving_weight = _clean_estimated_weight(weight_grams)
        for option_unit in ("g", "oz"):
            options.append(
                {
                    "key": option_unit,
                    "label": UNIT_OPTION_LABELS[option_unit],
                    "unit_label": UNIT_LABELS[option_unit],
                    "serving_multiplier": _decimal_string(
                        MASS_UNITS_IN_GRAMS[option_unit] / serving_weight
                    ),
                }
            )

    conversions = None
    base_canonical_quantity = None
    if unit in MASS_UNITS_IN_GRAMS:
        conversions = MASS_UNITS_IN_GRAMS
        base_canonical_quantity = base_quantity * conversions[unit]
    elif unit in VOLUME_UNITS_IN_MILLILITERS:
        conversions = VOLUME_UNITS_IN_MILLILITERS
        base_canonical_quantity = base_quantity * conversions[unit]
    elif volume_milliliters is not None:
        conversions = VOLUME_UNITS_IN_MILLILITERS
        base_canonical_quantity = _clean_estimated_volume(volume_milliliters)
    if conversions is None:
        return options

    for option_unit, canonical_quantity in conversions.items():
        options.append(
            {
                "key": option_unit,
                "label": UNIT_OPTION_LABELS[option_unit],
                "unit_label": UNIT_LABELS[option_unit],
                "serving_multiplier": _decimal_string(
                    canonical_quantity / base_canonical_quantity
                ),
            }
        )
    return options
