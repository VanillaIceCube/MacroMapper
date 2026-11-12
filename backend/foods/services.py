from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .identity import (
    canonical_food_identity,
    definition_fingerprint,
    digest,
    evidence_metadata,
)
from .models import (
    FoodComponent,
    FoodItem,
    FoodItemVersion,
    FoodVersionEvidence,
    SourceReference,
)


def build_component_map(root_version_ids):
    component_map = defaultdict(list)
    pending_version_ids = {vid for vid in root_version_ids if vid}
    visited_version_ids = set()
    while pending_version_ids:
        pending_version_ids -= visited_version_ids
        if not pending_version_ids:
            break
        components = list(
            FoodComponent.objects.filter(parent_version_id__in=pending_version_ids)
            .select_related("child_version__food_item")
            .prefetch_related("child_version__sources")
        )
        visited_version_ids.update(pending_version_ids)
        pending_version_ids = set()
        for component in components:
            component_map[component.parent_version_id].append(component)
            if component.child_version_id not in visited_version_ids:
                pending_version_ids.add(component.child_version_id)
    return component_map


@transaction.atomic
def create_food_item(
    *,
    name,
    scope,
    origin_type,
    provider_name,
    owner,
    definition,
    created_by,
    shared_fingerprint=None,
    canonical_identity=None,
    market="",
    product_identifier="",
    identity_url="",
):
    food_item = FoodItem(
        name=name,
        scope=scope,
        origin_type=origin_type,
        provider_name=provider_name,
        owner=owner,
        shared_fingerprint=shared_fingerprint,
        canonical_identity=canonical_identity,
        market=market,
        product_identifier=product_identifier,
        identity_url=identity_url,
    )
    food_item.full_clean()
    food_item.save()
    create_food_version(
        food_item=food_item,
        definition=definition,
        created_by=created_by,
    )
    return food_item


@transaction.atomic
def create_food_version(*, food_item, definition, created_by):
    locked_item = FoodItem.objects.select_for_update().get(pk=food_item.pk)
    next_version = (
        locked_item.versions.aggregate(highest=Max("version_number"))["highest"] or 0
    ) + 1

    fingerprint = definition_fingerprint(definition)
    if locked_item.scope == FoodItem.Scope.SHARED and locked_item.canonical_identity:
        existing = locked_item.versions.filter(content_fingerprint=fingerprint).first()
        if existing is not None:
            _add_version_evidence(existing, definition)
            _select_shared_current(locked_item)
            food_item.current_version = locked_item.current_version
            return existing

    definition = definition.copy()
    nutrients = definition.pop("nutrients", {})
    sources = definition.pop("sources", [])
    components = definition.pop("components", [])

    version = FoodItemVersion(
        food_item=locked_item,
        version_number=next_version,
        created_by=created_by,
        content_fingerprint=fingerprint,
        **nutrients,
        **definition,
    )
    version.full_clean()
    version.save()

    for source_data in sources:
        source = SourceReference(food_version=version, **source_data)
        source.full_clean()
        source.save()

    for component_data in components:
        component_data = component_data.copy()
        child_food = component_data.pop("food_item")
        pinned_child_version = component_data.pop("food_version", None)
        if child_food.pk == locked_item.pk:
            raise ValidationError(
                {"components": "A food cannot include itself as a component."}
            )
        child_version = pinned_child_version or child_food.current_version
        if child_version is None:
            raise ValidationError(
                {"components": f"{child_food.name} has no current definition."}
            )
        if child_version.food_item_id != child_food.pk:
            raise ValidationError(
                {"components": "A pinned component version must belong to its food."}
            )
        component = FoodComponent(
            parent_version=version,
            child_version=child_version,
            **component_data,
        )
        component.full_clean()
        component.save()

    _add_version_evidence(version, {**definition, "sources": sources})
    locked_item.current_version = version
    if locked_item.scope == FoodItem.Scope.SHARED and locked_item.canonical_identity:
        _select_shared_current(locked_item)
    locked_item.full_clean()
    locked_item.save(update_fields=["current_version", "updated_at"])
    food_item.current_version = locked_item.current_version
    food_item.updated_at = locked_item.updated_at
    return version


def _add_version_evidence(version, definition):
    metadata = evidence_metadata(definition)
    FoodVersionEvidence.objects.get_or_create(
        food_version=version,
        fingerprint=digest(metadata),
        defaults={"metadata": metadata},
    )
    for source_data in definition.get("sources", []):
        SourceReference.objects.get_or_create(
            food_version=version,
            url=source_data["url"],
            defaults={key: value for key, value in source_data.items() if key != "url"},
        )


def _select_shared_current(food):
    """Evidence quality wins, with the earliest version as a stable final tie-break."""
    from decimal import Decimal

    ranks = {
        "official": 4,
        "community_estimate": 3,
        "ai_estimate": 2,
        "user_entered": 1,
        "user_modified_estimate": 0,
    }

    def rank(version):
        evidence = [
            evidence_metadata(
                {
                    "provenance": version.provenance,
                    "confidence_score": version.confidence_score,
                }
            ),
            *[entry.metadata for entry in version.estimate_evidence.all()],
        ]
        provenance, confidence = max(
            (
                ranks.get(entry.get("provenance"), 0),
                Decimal(entry.get("confidence_score") or "0"),
            )
            for entry in evidence
        )
        return (
            provenance,
            len(version.sources.all()),
            confidence,
            -version.version_number,
            -version.pk,
        )

    versions = list(food.versions.prefetch_related("sources", "estimate_evidence"))
    if versions:
        food.current_version = max(versions, key=rank)
        food.save(update_fields=["current_version", "updated_at"])


@transaction.atomic
def publish_shared_food(*, item, definition):
    """The caller must validate all public item/source fields before publication."""
    from django.db import IntegrityError

    identity = canonical_food_identity(
        **{
            key: item.get(key, "")
            for key in (
                "name",
                "provider_name",
                "market",
                "product_identifier",
                "identity_url",
            )
        },
        origin_type=item.get("origin_type") or FoodItem.OriginType.GENERIC,
        sources=definition.get("sources", []),
    )
    food = (
        FoodItem.objects.select_for_update().filter(canonical_identity=identity).first()
    )
    if food is None:
        try:
            with transaction.atomic():
                food = FoodItem.objects.create(
                    name=item["name"],
                    scope=FoodItem.Scope.SHARED,
                    origin_type=item.get("origin_type") or FoodItem.OriginType.GENERIC,
                    provider_name=item.get("provider_name", ""),
                    canonical_identity=identity,
                    shared_fingerprint=identity,
                    market=item.get("market", ""),
                    product_identifier=item.get("product_identifier", ""),
                    identity_url=item.get("identity_url", ""),
                )
        except IntegrityError:
            food = FoodItem.objects.select_for_update().get(canonical_identity=identity)
    version = create_food_version(
        food_item=food, definition=definition, created_by=None
    )
    return food, version


@transaction.atomic
def consolidate_shared_foods(food_ids, *, apply=False):
    """Explicit, reversible-in-data archival; original versions/references never move."""
    from django.utils import timezone

    from .identity import version_definition

    foods = list(
        FoodItem.objects.select_for_update().filter(pk__in=food_ids).order_by("pk")
    )
    if len(foods) < 2 or len(foods) != len(set(food_ids)):
        raise ValidationError("Select at least two existing foods.")
    if any(
        food.scope != FoodItem.Scope.SHARED or food.archived_at or food.merged_into_id
        for food in foods
    ):
        raise ValidationError(
            "Only active shared foods may be consolidated; personal foods are preserved."
        )
    identities = {
        canonical_food_identity(
            name=food.name,
            provider_name=food.provider_name,
            origin_type=food.origin_type,
            market=food.market,
            product_identifier=food.product_identifier,
            identity_url=food.identity_url,
            sources=list(food.current_version.sources.values())
            if food.current_version_id
            else [],
        )
        for food in foods
    }
    if len(identities) != 1:
        raise ValidationError(
            "The selected foods have different canonical identities or product/market evidence. Review them separately."
        )
    identity = identities.pop()
    registered = FoodItem.objects.filter(canonical_identity=identity).first()
    if registered is not None and registered.pk not in food_ids:
        raise ValidationError(
            "Include the registered canonical food in the reviewed consolidation set."
        )
    canonical = registered or foods[0]
    if not apply:
        return canonical
    canonical.canonical_identity = identity
    canonical.save(update_fields=["canonical_identity", "updated_at"])
    # Backfill legacy canonical versions so equivalent incoming definitions are reused.
    for version in canonical.versions.all():
        definition = version_definition(version)
        if not version.content_fingerprint:
            version.content_fingerprint = definition_fingerprint(definition)
            version.save(update_fields=["content_fingerprint"])
        _add_version_evidence(version, definition)
    for duplicate in foods:
        if duplicate.pk == canonical.pk:
            continue
        for original in duplicate.versions.order_by("version_number", "pk"):
            definition = version_definition(original)
            definition["derived_from"] = original
            cloned = create_food_version(
                food_item=canonical,
                definition=definition,
                created_by=original.created_by,
            )
            for evidence in original.estimate_evidence.all():
                FoodVersionEvidence.objects.get_or_create(
                    food_version=cloned,
                    fingerprint=evidence.fingerprint,
                    defaults={"metadata": evidence.metadata},
                )
        duplicate.merged_into = canonical
        duplicate.archived_at = timezone.now()
        duplicate.canonical_identity = None
        duplicate.save(
            update_fields=[
                "merged_into",
                "archived_at",
                "canonical_identity",
                "updated_at",
            ]
        )
    _select_shared_current(canonical)
    return canonical
