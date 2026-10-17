"""Form mixins shared across the project."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.organizations import scoping


class UserStampMixin:
    """Mixin para establecer el usuario creador y actualizador en un formulario."""

    def form_valid(self, form):
        instance = form.instance

        if hasattr(instance, "created_by") and not instance.pk:
            instance.created_by = self.request.user

        if hasattr(instance, "updated_by"):
            instance.updated_by = self.request.user

        self._assign_organization(instance)

        return super().form_valid(form)

    def _assign_organization(self, instance) -> None:
        """Assign the creator's organization to a tenant-owned instance.

        Reports inherit the organization from their machine; other models use
        the acting user's organization. Existing values are never overwritten.
        """
        if not hasattr(instance, "organization_id"):
            return
        if instance.organization_id is not None:
            return

        machine = getattr(instance, "machine", None)
        machine_organization_id = getattr(machine, "organization_id", None)
        if machine_organization_id is not None:
            instance.organization_id = machine_organization_id
            return

        organization = getattr(self.request.user, "organization", None)
        if organization is not None:
            instance.organization_id = organization.id


class OrganizationScopeFormMixin:
    """Expose a scoped ``organization`` field on tenant-owned model forms.

    The field is removed when the acting user cannot choose among several
    organizations (no ``user``, or a leaf organization). Without the field the
    key never reaches ``cleaned_data``, so the current owner is preserved
    instead of being cleared.
    """

    def __init__(self, *args, user=None, **kwargs) -> None:
        """Scope the organization field to the acting user.

        Args:
            *args: Positional arguments forwarded to ``ModelForm``.
            user: The acting user, used to scope the organization choices.
            **kwargs: Keyword arguments forwarded to ``ModelForm``.
        """
        super().__init__(*args, **kwargs)
        self.user = user
        field = self.fields.get("organization")
        if field is None:
            return
        if user is None or not scoping.can_choose_organization(user):
            self.fields.pop("organization")
            return
        field.queryset = scoping.visible_organizations(user)
        field.label = _("Client")
        field.empty_label = _("Own organization")

    def clean_organization(self):
        """Reject organizations outside the acting user's subtree."""
        organization = self.cleaned_data.get("organization")
        if organization is not None and not scoping.is_organization_visible(
            self.user, organization
        ):
            raise ValidationError(_("You cannot use that client."), code="invalid")
        return organization

    def clean(self):
        """Treat an empty selection as "no change" instead of a clear."""
        cleaned = super().clean()
        if "organization" in self.fields and not cleaned.get("organization"):
            cleaned["organization"] = getattr(self.instance, "organization", None)
        return cleaned
