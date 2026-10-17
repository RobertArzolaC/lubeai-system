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
