from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from providers import views as providers_views
from django.views.generic.base import RedirectView # Adicione este import

urlpatterns = [
    path('', RedirectView.as_view(url='/login/'), name='index'),
    
    path('admin/', admin.site.urls),
    
    path('usuarios/', providers_views.gestao_usuarios, name='gestao_usuarios'),
    
    # Login/Logout
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # 3. HOME (Para onde o usuário vai DEPOIS de logar)
    path('home/', providers_views.home_view, name='home'),
    
    # Home e Cadastro
    path('cadastro/', providers_views.lista_provedores, name='cadastro'),    
    
    # Gestão de Provedores
    path('provedores/', providers_views.lista_provedores, name='lista_provedores'), 
    path('provedores/novo/', providers_views.editar_provedor, name='cadastrar_provedor'),
    path('provedores/editar/<int:pk>/', providers_views.editar_provedor, name='editar_provedor'),
    path('provedores/excluir/<int:pk>/', providers_views.excluir_provedor, name='excluir_provedor'),
    
    # Gestão de Contatos (Adicionado Editar)
    path('provedores/<int:provedor_id>/contato/novo/', providers_views.adicionar_contato, name='adicionar_contato'),
    path('provedores/contato/editar/<int:contato_id>/', providers_views.editar_contato, name='editar_contato'), # Nova!
    path('provedores/contato/excluir/<int:contato_id>/', providers_views.excluir_contato, name='excluir_contato'),
    
    # Gestão de Cidades
    path('provedores/<int:provedor_id>/cidade/nova/', providers_views.adicionar_cidade, name='adicionar_cidade'),
    path('provedores/cidade/excluir/<int:cidade_id>/', providers_views.excluir_cidade, name='excluir_cidade'),
    path('provedores/<int:provedor_id>/cidades/limpar/', providers_views.excluir_todas_cidades, name='excluir_todas_cidades'),
    
    # Consultas e Mapeamento (Nome corrigido para o template)
    path('importar-mapeamento/', providers_views.importar_e_mapear_projeto, name='importar_mapeamento'),
    path('consulta/', providers_views.consulta_provedores, name='consulta'), 
    path('consulta/mapeamento/', providers_views.consulta_provedores, name='consulta_provedores'), 
    path('provedores/importar-cidades/<int:provedor_id>/', providers_views.importar_cidades_csv, name='importar_cidades_csv'),
    path('custo-medio/', providers_views.processar_custo_medio, name='processar_custo_medio'),
    
    # Gestão de Usuários (Centralizado)
    path('usuarios/', providers_views.gestao_usuarios, name='gestao_usuarios'),
    path('usuarios/novo/', providers_views.criar_usuario, name='criar_usuario'),
    path('usuarios/excluir/<int:user_id>/', providers_views.excluir_usuario, name='excluir_usuario'),
    path('usuarios/senha/<int:user_id>/', providers_views.alterar_senha, name='alterar_senha'),
]