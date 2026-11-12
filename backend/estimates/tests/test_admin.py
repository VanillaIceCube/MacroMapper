from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from ..admin import MealProposalRevisionAdmin
from ..models import MealProposalRevision


class MealProposalAdminTests(TestCase):
    def test_standalone_revision_admin_is_immutable(self):
        revision_admin = MealProposalRevisionAdmin(
            MealProposalRevision,
            AdminSite(),
        )
        request = RequestFactory().get("/admin/estimates/mealproposalrevision/")

        self.assertFalse(revision_admin.has_add_permission(request))
        self.assertFalse(revision_admin.has_change_permission(request))
        self.assertFalse(revision_admin.has_delete_permission(request))
