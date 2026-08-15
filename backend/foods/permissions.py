from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import FoodItem


class IsPersonalFoodOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, food_item):
        if request.method in SAFE_METHODS:
            return True
        return (
            food_item.scope == FoodItem.Scope.PERSONAL
            and food_item.owner_id == request.user.id
        )
