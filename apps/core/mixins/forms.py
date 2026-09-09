class UserStampMixin:
    """
    Mixin para establecer el usuario creador y actualizador en un formulario.
    """

    def form_valid(self, form):
        if hasattr(form.instance, "created_by") and not form.instance.pk:
            form.instance.created_by = self.request.user

        if hasattr(form.instance, "updated_by"):
            form.instance.updated_by = self.request.user

        return super().form_valid(form)
