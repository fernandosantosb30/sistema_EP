from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PrestadorServico',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('razao_social', models.CharField(max_length=255)),
                ('nome_fantasia', models.CharField(max_length=255)),
                ('cnpj', models.CharField(blank=True, db_index=True, max_length=18, null=True, unique=True)),
                ('contato', models.CharField(max_length=100)),
                ('telefone', models.CharField(max_length=20)),
                ('email', models.EmailField(max_length=254)),
                ('instalacao_satelite', models.BooleanField(default=False)),
                ('teste_rede', models.BooleanField(default=False)),
                ('possui_documentacao', models.BooleanField(default=False)),
                ('observacoes', models.TextField(blank=True)),
                ('data_cadastro', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Prestador de serviço', 'verbose_name_plural': 'Prestadores de serviço', 'ordering': ['nome_fantasia']},
        ),
        migrations.CreateModel(
            name='CidadeAtendidaPrestador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(db_index=True, max_length=100)),
                ('uf', models.CharField(db_index=True, max_length=2)),
                ('prestador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cidades_atendidas', to='providers.prestadorservico')),
            ],
            options={'verbose_name': 'Cidade atendida pelo prestador', 'verbose_name_plural': 'Cidades atendidas pelos prestadores', 'unique_together': {('prestador', 'nome', 'uf')}},
        ),
    ]
