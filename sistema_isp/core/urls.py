from django.contrib import admin
from django.urls import path, include # Importante ter o 'include'
from providers import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('cadastro/', views.lista_provedores, name='cadastro'),
    path('consulta/', views.consulta_provedores, name='consulta'),
    path('provedores/novo/', views.editar_provedor, name='novo_provedor'),
    path('provedores/editar/<int:pk>/', views.editar_provedor, name='editar_provedor'),
    path('provedores/excluir/<int:pk>/', views.excluir_provedor, name='excluir_provedor'),
]