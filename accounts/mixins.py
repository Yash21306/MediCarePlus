from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect('login')

        if not request.user.is_approved:
            return redirect('pending')

        if request.user.role not in self.allowed_roles:
            return redirect('home')

        return super().dispatch(request, *args, **kwargs)