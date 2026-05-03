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
    path('provedores/<int:provedor_id>/contato/novo/', views.adicionar_contato, name='adicionar_contato'),
    path('contato/excluir/<int:contato_id>/', views.excluir_contato, name='excluir_contato'),
    path('contato/editar/<int:contato_id>/', views.editar_contato_action, name='editar_contato_action'),
    path('cidade/nova/<int:provedor_id>/', views.adicionar_cidade, name='adicionar_cidade'),
    path('cidade/importar/<int:provedor_id>/', views.importar_cidades_csv, name='importar_cidades_csv'),
    path('cidade/excluir/<int:cidade_id>/', views.excluir_cidade, name='excluir_cidade'),
    path('provedor/<int:provedor_id>/cidades/limpar/', views.excluir_todas_cidades, name='excluir_todas_cidades'),
]