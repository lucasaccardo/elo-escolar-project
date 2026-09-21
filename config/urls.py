from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'contas/login/',
        auth_views.LoginView.as_view(redirect_authenticated_user=True),
        name='login',
    ),
    path('contas/', include('django.contrib.auth.urls')),
    path('acessos/', include('acessos.urls')),
    path('', include('relatorios.urls')),
]