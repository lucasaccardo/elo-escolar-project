from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('contas/', include('django.contrib.auth.urls')),
    path('acessos/', include('acessos.urls')),
    path('', include('relatorios.urls')),
]