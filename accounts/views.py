from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import RegisterForm
class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('login')
