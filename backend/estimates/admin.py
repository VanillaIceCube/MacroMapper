from django.contrib import admin

from .models import MealProposal


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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
