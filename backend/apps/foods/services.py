"""Catalog, versioning and actor-scoped food services shared by REST and MCP."""

from collections import defaultdict

from django.core.exceptions import ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import (
    Case,
    DateField,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.utils import timezone
from django.utils.text import smart_split, unescape_string_literal
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.fields import CharField

from apps.meals.models import MealItem

from .evidence import usable_nutrition
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
from .nutrients import NUTRIENT_FIELDS


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


def _version_has_nutrition(version, visited=None):
    if version is None:
        return False
    visited = set(visited or ())
    if version.pk in visited:
        return False
    if usable_nutrition({field: getattr(version, field) for field in NUTRIENT_FIELDS}):
        return True
    return any(
        _version_has_nutrition(component.child_version, visited | {version.pk})
        for component in version.components.select_related("child_version")
    )


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

    if locked_item.scope == FoodItem.Scope.SHARED:
        children_usable = [
            _version_has_nutrition(
                component.get("food_version") or component["food_item"].current_version
            )
            for component in definition.get("components", [])
        ]
        if not all(children_usable) or not (
            usable_nutrition(definition.get("nutrients", {})) or any(children_usable)
        ):
            raise ValidationError(
                {
                    "nutrients": "Shared foods require usable nutrition; no food was published."
                }
            )

    candidate_fields = definition.copy()
    candidate_nutrients = candidate_fields.pop("nutrients", {})
    candidate_fields.pop("sources", None)
    candidate_fields.pop("components", None)
    # Deduplication must retain the same validation gate as inserting a new version.
    FoodItemVersion(
        food_item=locked_item,
        version_number=next_version,
        created_by=created_by,
        **candidate_nutrients,
        **candidate_fields,
    ).full_clean()
    fingerprint = definition_fingerprint(definition)
    if locked_item.scope == FoodItem.Scope.SHARED and locked_item.canonical_identity:
        existing = locked_item.versions.filter(content_fingerprint=fingerprint).first()
        if existing is not None:
            for source_data in definition.get("sources", []):
                SourceReference(food_version=existing, **source_data).full_clean(
                    validate_unique=False, validate_constraints=False
                )
            for component_data in definition.get("components", []):
                child = component_data["food_item"]
                child_version = (
                    component_data.get("food_version") or child.current_version
                )
                if child_version is None or child_version.food_item_id != child.pk:
                    raise ValidationError(
                        {
                            "components": "A pinned component version must belong to its food."
                        }
                    )
                FoodComponent(
                    parent_version=existing,
                    child_version=child_version,
                    servings=component_data["servings"],
                    order=component_data.get("order", 0),
                ).full_clean(validate_unique=False, validate_constraints=False)
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
        coverage = version.evidence.get("nutrients", {})
        verified_count = sum(
            field.get("status") == "official_verified" for field in coverage.values()
        )
        verification_rank = {
            "official_verified": 3,
            "source_backed_ai_components": 3,
            "partially_source_backed": 2,
            "ai_estimate": 1,
        }.get(version.evidence.get("status"), 0)
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
            verification_rank,
            verified_count,
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


def foods_for(actor, query=None, *, retrieve=False):
    query = query or {}
    available = FoodItem.objects.active()
    if retrieve:
        available = FoodItem.objects.filter(
            Q(archived_at__isnull=True)
            | Q(
                scope=FoodItem.Scope.SHARED,
                merged_into__scope=FoodItem.Scope.SHARED,
                merged_into__archived_at__isnull=True,
                merged_into__isnull=False,
            )
        )
    queryset = (
        available.visible_to(actor)
        .select_related("owner", "current_version")
        .prefetch_related("current_version__sources")
    )
    latest_log = (
        MealItem.objects.filter(
            meal_entry__owner=actor,
            food_version__food_item_id=OuterRef("pk"),
        )
        .order_by(
            "-meal_entry__entry_date",
            "-meal_entry__created_at",
            "-id",
        )
        .values("meal_entry__entry_date")[:1]
    )
    queryset = queryset.annotate(
        last_logged_on=Subquery(latest_log, output_field=DateField())
    ).annotate(
        has_logged=Case(
            When(last_logged_on__isnull=False, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )
    search_query = query.get("search", "").strip()
    if search_query:
        queryset = queryset.annotate(
            relevance=Case(
                When(name__iexact=search_query, then=Value(0)),
                When(name__istartswith=search_query, then=Value(1)),
                When(provider_name__iexact=search_query, then=Value(2)),
                When(name__icontains=search_query, then=Value(3)),
                When(provider_name__istartswith=search_query, then=Value(4)),
                default=Value(5),
                output_field=IntegerField(),
            )
        )
    else:
        queryset = queryset.annotate(relevance=Value(0, output_field=IntegerField()))
    scope = query.get("scope", "").strip()
    if scope:
        if scope not in FoodItem.Scope.values:
            raise APIValidationError({"scope": "Choose personal or shared."})
        queryset = queryset.filter(scope=scope)

    provider = query.get("provider", "").strip()
    if provider:
        queryset = queryset.filter(provider_name__icontains=provider)

    provenance = query.get("provenance", "").strip()
    if provenance:
        requested = {value.strip() for value in provenance.split(",") if value.strip()}
        invalid = requested - set(FoodItemVersion.Provenance.values)
        if invalid:
            raise APIValidationError({"provenance": "Choose a valid provenance."})
        queryset = queryset.filter(current_version__provenance__in=requested)

    origin_type = query.get("origin_type", "").strip()
    if origin_type:
        if origin_type not in FoodItem.OriginType.values:
            raise APIValidationError({"origin_type": "Choose a valid food type."})
        queryset = queryset.filter(origin_type=origin_type)
    return filter_foods(queryset, query)


def require_personal_owner(actor, food):
    if food.scope != FoodItem.Scope.PERSONAL or food.owner_id != actor.pk:
        raise PermissionDenied("You do not have permission to perform this action.")
    if food.archived_at is not None:
        raise PermissionDenied("This food is no longer available.")


def _validation_details(error):
    return (
        error.message_dict
        if hasattr(error, "message_dict")
        else {"detail": error.messages}
    )


def create_personal_food(actor, data):
    data = validate_food_data(actor, dict(data))
    definition = data.pop("definition")
    try:
        return create_food_item(
            scope=FoodItem.Scope.PERSONAL,
            owner=actor,
            created_by=actor,
            definition=definition,
            **data,
        )
    except DjangoValidationError as error:
        raise APIValidationError(_validation_details(error)) from error


@transaction.atomic
def update_personal_food(actor, food, data):
    food = FoodItem.objects.select_for_update().get(pk=food.pk)
    require_personal_owner(actor, food)
    data = validate_food_data(actor, dict(data), food)
    definition = data.pop("definition", None)
    try:
        for field, value in data.items():
            setattr(food, field, value)
        food.full_clean()
        food.save()
        if definition is not None:
            create_food_version(food_item=food, definition=definition, created_by=actor)
        return food
    except DjangoValidationError as error:
        raise APIValidationError(_validation_details(error)) from error


@transaction.atomic
def archive_personal_food(actor, food):
    food = FoodItem.objects.select_for_update().get(pk=food.pk)
    require_personal_owner(actor, food)
    food.archived_at = timezone.now()
    food.save(update_fields=["archived_at", "updated_at"])


def validate_food_data(actor, attrs, instance=None):
    for component in (attrs.get("definition") or {}).get("components", []):
        food = component["food_item"]
        if (
            not FoodItem.objects.active()
            .visible_to(actor)
            .filter(pk=food.pk, current_version__isnull=False)
            .exists()
        ):
            raise APIValidationError(
                {"definition": {"components": "This food is not available."}}
            )
    definition = attrs.get("definition")
    if instance is None and definition is None:
        raise APIValidationError({"definition": "A food definition is required."})
    if instance is not None and definition:
        if any(
            item["food_item"].pk == instance.pk
            for item in definition.get("components", [])
        ):
            raise APIValidationError(
                {"definition": {"components": "A food cannot include itself."}}
            )

    name = attrs.get("name", getattr(instance, "name", "")).strip()
    if not name:
        raise APIValidationError({"name": "This field may not be blank."})
    attrs["name"] = name

    provider_name = attrs.get(
        "provider_name",
        getattr(instance, "provider_name", ""),
    ).strip()
    attrs["provider_name"] = provider_name
    origin_type = attrs.get(
        "origin_type",
        getattr(instance, "origin_type", FoodItem.OriginType.GENERIC),
    )
    if (
        origin_type
        in {
            FoodItem.OriginType.BRANDED,
            FoodItem.OriginType.RESTAURANT,
        }
        and not provider_name
    ):
        raise APIValidationError(
            {"provider_name": "Branded and restaurant foods require a provider."}
        )
    return attrs


def filter_foods(rows, query):
    """The catalog's existing token/quoted-phrase search and allowed ordering."""
    terms = []
    search = CharField(trim_whitespace=False, allow_blank=True).run_validation(
        query.get("search", "")
    )
    for term in smart_split(search):
        term = term.strip(",")
        if term.startswith(('"', "'")) and term[0] == term[-1]:
            terms.append(unescape_string_literal(term))
        else:
            terms.extend(part.strip() for part in term.split(",") if part)
    if terms:
        matched = rows
        for term in terms:
            matched = matched.filter(
                Q(name__icontains=term)
                | Q(provider_name__icontains=term)
                | Q(current_version__sources__title__icontains=term)
                | Q(current_version__sources__provider__icontains=term)
            )
        # Keep the same correlated existence policy as the REST search backend.
        from django.db.models import Exists

        rows = rows.filter(Exists(matched.filter(pk=OuterRef("pk"))))
    allowed = {
        "id",
        "name",
        "created_at",
        "updated_at",
        "relevance",
        "has_logged",
        "last_logged_on",
    }
    ordering = [
        field.strip()
        for field in query.get("ordering", "name,id").split(",")
        if field.strip().lstrip("-") in allowed
    ]
    return rows.order_by(*(ordering or ["name", "id"]))
