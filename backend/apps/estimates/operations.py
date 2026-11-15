"""Validated edits to a draft tree; catalog definitions are never mutated here."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


def positive_decimal(value, *, maximum=None):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValidationError("Supply a valid positive portion.") from error
    if (
        not number.is_finite()
        or number < Decimal("0.0001")
        or (maximum and number > maximum)
    ):
        raise ValidationError(
            "Supply a valid positive portion within the allowed range."
        )
    if number > Decimal("999999.9999"):
        raise ValidationError("The portion is too large.")
    return number


def index_tree(items):
    indexed = {}

    def visit(nodes, depth):
        if not nodes:
            return
        if depth > 4 or len(nodes) > (20 if depth == 0 else 30):
            raise ValidationError("Meal hierarchy exceeds its depth or item limit.")
        for node in nodes:
            key = node["key"]
            if key in indexed:
                raise ValidationError("Each meal ingredient must occur exactly once.")
            indexed[key] = (node, nodes)
            visit(node.get("components", []), depth + 1)

    visit(items, 0)
    return indexed


def apply_tree_operations(items, result):
    """Apply absolute edits, preserving stable keys and per-recipe child quantities."""
    indexed = index_tree(items)
    moves = result.get("reparentings") or []
    changed = False
    moved = set()
    for move in moves:
        key, parent_key = move.get("key"), move.get("parent_key")
        if key not in indexed or (parent_key is not None and parent_key not in indexed):
            raise ValidationError("Choose an existing ingredient and destination food.")
        if key in moved:
            raise ValidationError("Move each ingredient only once per correction.")
        moved.add(key)
        node, siblings = indexed[key]
        if parent_key in index_tree([node]):
            raise ValidationError("An ingredient cannot contain itself or its parent.")
        if parent_key is not None and not indexed[parent_key][0].get("components"):
            raise ValidationError(
                "Choose a composite food as the ingredient destination."
            )
        destination = (
            items
            if parent_key is None
            else indexed[parent_key][0].setdefault("components", [])
        )
        if destination is not siblings:
            if any(
                (
                    node.get("food_item_id")
                    and child.get("food_item_id") == node["food_item_id"]
                )
                or (
                    node.get("food_version_id")
                    and child.get("food_version_id") == node["food_version_id"]
                )
                for child in destination
            ):
                raise ValidationError(
                    "That ingredient already exists at the destination. Adjust its quantity or remove the duplicate first."
                )
            siblings.remove(node)
            destination.append(node)
            changed = True
            indexed = index_tree(items)

    excluded = set()
    fraction_targets = set()
    fraction_children = set()
    fractions = result.get("fraction_updates") or []
    for update in fractions:
        key = update.get("key")
        if key not in indexed or not indexed[key][0].get("components"):
            raise ValidationError("Choose an existing recipe for a consumed fraction.")
        if key in fraction_targets or key in fraction_children:
            raise ValidationError(
                "Supply one consumed fraction per recipe, without scaling its children."
            )
        fraction_targets.add(key)
        fraction = positive_decimal(update.get("fraction"), maximum=Decimal("1"))
        exemptions = set(update.get("excluded_keys") or [])
        if not exemptions.issubset(indexed) or key in exemptions:
            raise ValidationError(
                "Choose existing separate foods to exclude from the fraction."
            )
        descendants = set(index_tree(indexed[key][0]["components"]))
        if descendants & fraction_targets:
            raise ValidationError(
                "Apply a consumed fraction only once along an ingredient path."
            )
        fraction_children.update(descendants)
        if exemptions & descendants:
            raise ValidationError(
                "Move excluded ingredients outside the recipe before scaling it."
            )
        excluded.update(exemptions)
        indexed[key][0]["servings"] = str(fraction)
        changed = True

    updates = result.get("serving_updates") or []
    seen = set()
    for update in updates:
        key = update.get("key")
        if key in excluded:
            continue
        if key in fraction_targets or key in fraction_children:
            raise ValidationError(
                "Keep recipe quantities separate from its consumed fraction."
            )
        if key not in indexed:
            raise ValidationError("Choose an existing food for a quantity correction.")
        if key in seen:
            raise ValidationError("Supply one quantity correction per food.")
        seen.add(key)
        indexed[key][0]["servings"] = str(positive_decimal(update.get("servings")))
        changed = True

    for update in result.get("portion_updates") or []:
        key = update.get("key")
        if key in excluded:
            continue
        if key in fraction_targets or key in fraction_children:
            raise ValidationError(
                "Keep serving-size edits separate from a recipe fraction correction."
            )
        if key not in indexed:
            raise ValidationError(
                "Choose an existing food for a serving-size correction."
            )
        node = indexed[key][0]
        options = {option["key"]: option for option in node.get("portion_options", [])}
        selected = update.get("portion_key")
        if selected not in options:
            raise ValidationError("Choose an available portion option.")
        previous = node.get("selected_portion_key", "base")
        if selected.startswith("size:") and (
            previous.startswith("size:")
            or (
                previous == "base"
                and node.get("serving_unit")
                not in {"g", "oz", "ml", "fl_oz", "cup", "tbsp", "tsp"}
            )
        ):
            old = options.get(previous, {"serving_multiplier": "1"})
            count = positive_decimal(node["servings"]) / positive_decimal(
                old["serving_multiplier"]
            )
            node["servings"] = str(
                count * positive_decimal(options[selected]["serving_multiplier"])
            )
        node["selected_portion_key"] = selected
        changed = True

    # Remove descendants through their owning list, without leaving stale totals
    # when the last child of an existing composite was removed or moved.
    for key in result.get("remove_keys") or []:
        indexed = index_tree(items)
        if key not in indexed:
            raise ValidationError("Choose an existing ingredient to remove.")
        node, siblings = indexed[key]
        siblings.remove(node)
        changed = True
    index_tree(items)
    return changed
