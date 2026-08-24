from django.contrib import admin

from .models import MealProposal, MealProposalRevision


class MealProposalRevisionInline(admin.TabularInline):
    model = MealProposalRevision
    extra = 0
    fields = (
        "revision_number",
        "kind",
        "message",
        "parent_revision",
        "created_by",
        "created_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MealProposal)
class MealProposalAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "entry_date",
        "status",
        "generator",
        "provider_model",
        "created_at",
    )
    list_filter = ("status", "generator", "entry_date")
    search_fields = ("name", "description", "owner__email")
    readonly_fields = (
        "owner",
        "description",
        "entry_date",
        "name",
        "status",
        "generator",
        "provider_name",
        "provider_model",
        "provider_response_id",
        "confidence_score",
        "items",
        "accepted_meal",
        "accepted_at",
        "created_at",
        "updated_at",
    )
    inlines = (MealProposalRevisionInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MealProposalRevision)
class MealProposalRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "proposal",
        "revision_number",
        "kind",
        "created_by",
        "created_at",
    )
    list_filter = ("kind", "created_at")
    search_fields = ("proposal__name", "proposal__owner__email")
    readonly_fields = (
        "proposal",
        "revision_number",
        "kind",
        "name",
        "items",
        "message",
        "parent_revision",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
