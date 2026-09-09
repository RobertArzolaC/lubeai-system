"""Tests for the ``apps.core.mixins.forms`` module."""

from django import forms
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TransactionTestCase
from django.views.generic import CreateView

from apps.core import models as core_models
from apps.core.mixins.forms import UserStampMixin
from apps.users.factories import UserFactory


class StampedThing(core_models.BaseUserTracked):
    """Concrete model with creator/updater tracking fields."""

    class Meta:
        app_label = "core"


class StampedForm(forms.ModelForm):
    """Form used to create/update a :class:`StampedThing`."""

    class Meta:
        model = StampedThing
        fields: tuple[str, ...] = ()


class StampedCreateView(UserStampMixin, CreateView):
    """Minimal create view wired to :class:`UserStampMixin`."""

    model = StampedThing
    fields: tuple[str, ...] = ()
    success_url = "/"


class UserStampMixinTests(TransactionTestCase):
    """Tests for the :class:`UserStampMixin`."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        with connection.schema_editor() as editor:
            editor.create_model(StampedThing)

    @classmethod
    def tearDownClass(cls) -> None:
        with connection.schema_editor() as editor:
            editor.delete_model(StampedThing)
        super().tearDownClass()

    def setUp(self) -> None:
        self.admin = UserFactory(is_staff=True, is_superuser=True)
        self.factory = RequestFactory()

    def build_request(self, user) -> None:
        """Attach an authenticated user to a factory request."""
        request = self.factory.post("/")
        request.user = user
        return request

    def test_form_valid_stamps_creator_and_updater(self) -> None:
        """A new object records the request user as creator and updater."""
        view = StampedCreateView()
        view.request = self.build_request(self.admin)
        view.object = None
        form = StampedForm(data={})
        self.assertTrue(form.is_valid())
        response = view.form_valid(form)
        self.assertIsInstance(response, HttpResponse)
        obj = StampedThing.objects.get()
        self.assertEqual(obj.created_by, self.admin)
        self.assertEqual(obj.updated_by, self.admin)

    def test_form_valid_only_updates_updater_for_existing(self) -> None:
        """Existing objects only refresh the ``updated_by`` stamp."""
        creator = UserFactory()
        editor = UserFactory(is_staff=True, is_superuser=True)
        existing = StampedThing.objects.create(created_by=creator, updated_by=creator)
        view = StampedCreateView()
        view.request = self.build_request(editor)
        form = StampedForm(data={}, instance=existing)
        self.assertTrue(form.is_valid())
        view.form_valid(form)
        existing.refresh_from_db()
        self.assertEqual(existing.created_by, creator)
        self.assertEqual(existing.updated_by, editor)
