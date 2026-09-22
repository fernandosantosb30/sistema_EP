from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PrestadorServico, CidadeAtendidaPrestador


class FluxosAcessoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', password='Senha-forte-987!')
        self.usuario = User.objects.create_user('comum', password='Senha-antiga-987!')

    def test_login_home_e_expiracao_absoluta(self):
        self.assertRedirects(self.client.get('/'), '/login/')
        response = self.client.post('/login/?next=/usuarios/', {
            'username': 'admin', 'password': 'Senha-forte-987!',
        })
        self.assertRedirects(response, '/home/')
        expiry = self.client.session.get_expiry_date()
        self.assertAlmostEqual((expiry - timezone.now()).total_seconds(), 86400, delta=10)
        self.assertRedirects(self.client.get('/'), '/home/')
        self.assertRedirects(self.client.get('/login/'), '/home/')
        self.client.get('/usuarios/')
        self.assertEqual(self.client.session.get_expiry_date(), expiry)
        from django.contrib.sessions.models import Session
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1))
        self.assertRedirects(self.client.get('/'), '/login/')

    def test_edicao_senha_autoridade_e_permissoes(self):
        url = reverse('editar_usuario', args=[self.usuario.pk])
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(url, {'autoridade': 'admin'}).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, {'autoridade': 'admin'}).status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_superuser)
        self.assertTrue(self.usuario.check_password('Senha-antiga-987!'))
        response = self.client.post(url, {'autoridade': 'usuario', 'new_password1': 'Senha-nova-456!', 'new_password2': 'diferente'})
        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_superuser)
        self.assertEqual(self.client.post(url, {'autoridade': 'usuario', 'new_password1': 'Senha-nova-456!', 'new_password2': 'Senha-nova-456!'}).status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_superuser)
        self.assertTrue(self.usuario.check_password('Senha-nova-456!'))

    def test_uf_combina_busca_sem_duplicatas(self):
        self.client.force_login(self.usuario)
        for number in range(12):
            prestador = PrestadorServico.objects.create(nome_fantasia=f'Empresa {number}', razao_social='Empresa')
            for cidade in ['Porto Alegre', 'Canoas']:
                CidadeAtendidaPrestador.objects.create(prestador=prestador, nome=cidade, uf='RS')
        prestador = PrestadorServico.objects.create(nome_fantasia='Empresa SP', razao_social='Empresa')
        CidadeAtendidaPrestador.objects.create(prestador=prestador, nome='São Paulo', uf='SP')
        response = self.client.get(reverse('lista_prestadores_servico'), {'uf': ' rs ', 'q': 'Empresa'})
        self.assertEqual(response.context['total_registros'], 12)
        self.assertContains(response, '&uf=RS')
        response = self.client.get(reverse('lista_prestadores_servico'), {'uf': 'SP', 'q': 'inexistente'})
        self.assertEqual(response.context['total_registros'], 0)

    def test_extracao_removida(self):
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get('/home/'), 'Extração Rápida')
        self.assertEqual(self.client.get('/coleta-dados/').status_code, 404)


class InstalacaoLocalTests(TestCase):
    def test_esquema_completo_e_paginas_principais(self):
        from django.apps import apps
        for model in apps.get_app_config('providers').get_models():
            self.assertEqual(model.objects.count(), 0)
        admin = User.objects.create_superuser('demo-admin', password='Senha-teste-987!')
        self.client.force_login(admin)
        for url in ['/home/', '/provedores/', '/provedores/novo/', '/prestadores-servico/', '/prestadores-servico/novo/', '/consulta/', '/custo-medio/', '/usuarios/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_carga_demonstrativa_repetida_sem_duplicacao(self):
        from django.core.management import call_command
        from django.test import override_settings
        from .models import Provedor, ContratoCusto
        import io
        from django.db import connection
        from django.core.management.base import CommandError
        if connection.vendor != 'sqlite':
            with override_settings(DEBUG=True), self.assertRaises(CommandError):
                call_command('seed_demo', stdout=io.StringIO())
            return
        with override_settings(DEBUG=True):
            for _ in range(2):
                call_command('seed_demo', stdout=io.StringIO())
        self.assertEqual(Provedor.objects.count(), 1)
        self.assertEqual(PrestadorServico.objects.count(), 1)
        self.assertEqual(ContratoCusto.objects.count(), 1)
        self.assertEqual(User.objects.count(), 0)


class CorrecoesRegressaoTests(TestCase):
    def setUp(self):
        from .models import Provedor, Contato, CidadeAtendida
        self.admin = User.objects.create_superuser('gestor', password='Senha-teste-987!')
        self.client.force_login(self.admin)
        self.provedor = Provedor.objects.create(nome='Empresa Teste')
        self.contato = Contato.objects.create(provedor=self.provedor, nome='Contato Inicial')
        for cidade, uf in [('Canoas', 'RS'), ('Campinas', 'SP')]:
            CidadeAtendida.objects.create(provedor=self.provedor, nome=cidade, uf=uf)

    def upload(self, texto):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile('teste.csv', texto.encode('utf-8'), content_type='text/csv')

    def test_exclusoes_get_bloqueadas_e_csrf_obrigatorio(self):
        from django.test import Client
        from .models import Provedor
        prestador = PrestadorServico.objects.create(nome_fantasia='Fictício')
        outro = User.objects.create_user('outro')
        urls = [reverse('excluir_provedor', args=[self.provedor.pk]), reverse('excluir_contato', args=[self.contato.pk]), reverse('excluir_cidade', args=[self.provedor.cidades.first().pk]), reverse('excluir_todas_cidades', args=[self.provedor.pk]), reverse('excluir_prestador_servico', args=[prestador.pk]), reverse('excluir_usuario', args=[outro.pk])]
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for url in urls:
            self.assertEqual(client.get(url).status_code, 405)
            self.assertEqual(client.post(url).status_code, 403)
        self.assertTrue(Provedor.objects.filter(pk=self.provedor.pk).exists())
        client.get('/home/')
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post(urls[0], HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertFalse(Provedor.objects.filter(pk=self.provedor.pk).exists())

    def test_usuario_comum_nao_exclui(self):
        user = User.objects.create_user('comum')
        self.client.force_login(user)
        self.client.post(reverse('excluir_provedor', args=[self.provedor.pk]))
        self.provedor.refresh_from_db()

    def test_contato_edita_e_preserva_erro(self):
        url = reverse('editar_contato', args=[self.contato.pk])
        self.assertContains(self.client.get(url), 'Contato Inicial')
        response = self.client.post(url, {'nome': 'Novo', 'email': 'invalido'})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.context['form']['nome'].value(), 'Novo')
        self.assertEqual(self.client.post(url, {'nome': 'Novo', 'email': 'teste@example.invalid'}).status_code, 302)
        self.contato.refresh_from_db()
        self.assertEqual(self.contato.nome, 'Novo')

    def test_cobertura_mesma_uf_e_exportacao_multiplas_cidades(self):
        response = self.client.get('/consulta/', {'uf': 'RS', 'cidade1': 'Campinas'})
        self.assertEqual(len(response.context['mapeamento']), 0)
        params = {'cidade1': 'Canoas', 'cidade2': 'Campinas'}
        self.assertEqual(len(self.client.get('/consulta/', params).context['mapeamento']), 1)
        response = self.client.get('/exportar-mapeamento/', params)
        texto = response.content.decode('utf-8-sig')
        self.assertIn('CANOAS', texto)
        self.assertIn('CAMPINAS', texto)
        self.assertNotIn('\ufeff', texto)

    def test_custos_mesma_cidade_estados_distintos(self):
        from .models import ContratoCusto
        for uf, valor in [('SP',100), ('RS',900)]:
            ContratoCusto.objects.create(cidade='Santa Maria', uf=uf, tipo_servico='Link', velocidade='100', meio_fisico='Fibra', mensal=valor)
        response = self.client.post('/custo-medio/processar-lote/', {'arquivo_csv': self.upload('cidade;uf;tipo_servico;velocidade\nSanta Maria;RS;Link;100\n')})
        self.assertEqual(response.status_code, 200)
        self.assertIn(';900.0;Cidade', response.content.decode('utf-8-sig'))
        self.assertNotIn('\ufeff', response.content.decode('utf-8-sig'))
        headers = {'HTTP_X_REQUESTED_WITH':'XMLHttpRequest'}
        response = self.client.get('/custo-medio/', {'cidade':'Inexistente'}, **headers)
        self.assertEqual(response.json()['nivel'], 'Sem dados')
        self.assertEqual(response.json()['quantidade_contratos'], 0)
        self.assertEqual(self.client.get('/custo-medio/', {'cidade':'Santa Maria'}, **headers).status_code, 400)

    def test_importacao_cabecalhos_e_atomicidade(self):
        url = reverse('importar_cidades_csv', args=[self.provedor.pk])
        self.client.post(url, {'arquivo_csv':self.upload('uf;cidade\nRS;São Leopoldo\n')})
        self.assertTrue(self.provedor.cidades.filter(nome='SAO LEOPOLDO', uf='RS').exists())
        self.client.post(url, {'arquivo_csv':self.upload('cidade;uf\nCidade Nova;RS\nOutra;ZZ\n')})
        self.assertFalse(self.provedor.cidades.filter(nome='CIDADE NOVA').exists())

    def test_validacao_usuarios_preservada(self):
        response = self.client.post('/usuarios/novo/', {'username':'gestor','password1':'123','password2':'456'})
        self.assertTrue(response.context['form'].is_bound)
        self.assertTrue(response.context['form'].errors)
        response = self.client.post(reverse('alterar_senha', args=[self.admin.pk]), {'new_password1':'123','new_password2':'456'})
        self.assertTrue(response.context['form'].errors)

    def test_proprio_admin_nao_rebaixado_e_login_admin_expira(self):
        self.client.post(reverse('editar_usuario', args=[self.admin.pk]), {'autoridade':'usuario'})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)
        self.client.logout()
        self.client.post('/admin/login/?next=/admin/', {'username':'gestor','password':'Senha-teste-987!'})
        self.assertIsNotNone(self.client.session.get('_session_expiry'))
        self.assertAlmostEqual((self.client.session.get_expiry_date()-timezone.now()).total_seconds(),86400,delta=10)

    def test_velocidade_unidades_e_formula_csv(self):
        from .services.consultas import velocidade_normalizada, resposta_csv
        self.assertEqual(velocidade_normalizada('1 GB'), velocidade_normalizada('1000 MB'))
        self.assertNotEqual(velocidade_normalizada('1 GB'), velocidade_normalizada('1 MB'))
        self.assertIn("'=1+1", resposta_csv('teste.csv', [['=1+1']]).content.decode('utf-8-sig'))

    def test_mapeamento_importado_bom_unico_e_uf(self):
        response = self.client.post('/importar-mapeamento/', {'arquivo_cidades': self.upload('cidade;uf\nCanoas;RS\nCampinas;RS\n')})
        self.assertEqual(response.status_code, 200)
        texto = response.content.decode('utf-8-sig')
        self.assertIn('CANOAS', texto)
        self.assertNotIn('CAMPINAS', texto)
        self.assertNotIn('\ufeff', texto)

    def test_formulario_cidade_invalida_preserva_dados(self):
        response = self.client.post(reverse('adicionar_cidade', args=[self.provedor.pk]), {'nome':'Nova','uf':'ZZ'})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(response.context['form']['nome'].value(), 'Nova')
        self.assertFalse(self.provedor.cidades.filter(nome='NOVA').exists())


class ConfiguracaoPrivacidadeTests(TestCase):
    def test_apresentacao_configurada_sem_expor_credenciais(self):
        from django.test import override_settings
        with override_settings(SITE_NAME='Empresa Fictícia <teste>', PARTNER_LABEL='Rede Fictícia', GOOGLE_SHEETS_ID='identificador-privado-ficticio'):
            response = self.client.get('/login/')
        self.assertContains(response, 'EP Conexões - Login')
        self.assertNotContains(response, 'Empresa Fictícia <teste>')
        self.assertNotContains(response, 'identificador-privado-ficticio')

    def test_integracao_sem_configuracao_nao_conecta(self):
        from django.test import override_settings
        from unittest.mock import patch
        from .services.importador import sincronizar_dados_google_sheets
        with override_settings(GOOGLE_SHEETS_ID='', GOOGLE_APPLICATION_CREDENTIALS=''), patch('providers.services.importador.gspread.authorize') as authorize:
            ok, message = sincronizar_dados_google_sheets()
        self.assertFalse(ok)
        self.assertIn('não configurada', message)
        authorize.assert_not_called()

    def test_dominio_da_hospedagem_sem_valor_fixo(self):
        import subprocess
        import sys
        import os
        import json
        env = os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE='core.settings_local', DJANGO_ALLOWED_HOSTS='custom.example.invalid', RENDER_EXTERNAL_HOSTNAME='service.example.invalid')
        result = subprocess.run([sys.executable, '-c', 'import json; from core.settings import ALLOWED_HOSTS; print(json.dumps(ALLOWED_HOSTS))'], env=env, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), ['custom.example.invalid', 'service.example.invalid'])
