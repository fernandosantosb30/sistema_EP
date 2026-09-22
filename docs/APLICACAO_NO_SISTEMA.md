# Correções aplicadas ao sistema principal

As alterações estão no projeto principal, não somente em `public-review/`. A apresentação é configurada por variáveis de ambiente; os nomes de campos legados foram mantidos para compatibilidade com o banco. Não houve conexão ao banco do cliente, publicação ou deploy.

## Alterações

- Edição de contatos; exclusões por POST com CSRF; erros de formulários preservados.
- Cobertura e exportação com regras comuns; custo por cidade e UF sem mistura de localidades.
- Importações validadas, gravação transacional de cidades e CSV com BOM único.
- Proteção da própria conta administradora e expiração absoluta em todos os logins.
- Configuração de arquivos estáticos e segurança; retirada da conexão embutida no script de importação.
- Ambiente local separado com `local.py` e SQLite em `.local/`.

## Migrações

A nova 0002 cria as tabelas que estiverem ausentes. Para tabelas legadas já existentes em PostgreSQL, valida colunas, tipos, nulabilidade, chaves, unicidade, relacionamentos e índices esperados antes de registrar o estado. Divergências bloqueiam a migração. Não há renomeação da coluna de parceria no projeto principal.

A operação não exclui tabelas no rollback. Não use `migrate providers 0001` para tentar retornar: preserve uma cópia independente do backup e a revisão anterior. Se houver erro estrutural, não use `--fake`; analise a diferença em restauração privada. O banco real não foi inspecionado.

## Seu deploy manual

1. Faça e verifique o backup privado do banco antes do deploy.
2. Configure na hospedagem `DATABASE_URL` e uma chave própria em `DJANGO_SECRET_KEY` ou `SECRET_KEY` (nome anterior ainda aceito). Não há chave fixa de produção no código.
3. Confira o domínio em `DJANGO_ALLOWED_HOSTS`. Na Render, o domínio do serviço é obtido de RENDER_EXTERNAL_HOSTNAME; domínios personalizados precisam estar nessa variável de configuração.
4. Para HTTPS atrás de proxy confiável que sobrescreva `X-Forwarded-Proto`, configure `DJANGO_TRUST_PROXY=true`. Não ative para proxies não confiáveis. Confira redirecionamentos antes de liberar o sistema.
5. Execute `python manage.py migrate --plan` e a migração em uma restauração privada. O banco real pode ter diferenças em relação ao esquema de referência.
6. O comando de build existente agora também executa `collectstatic --noinput`; mantém `migrate --noinput`. Se o build da sua hospedagem foi personalizado fora do arquivo `render.yaml`, atualize o comando lá também.
7. Valide login, edição, filtros e exportação após seu deploy.

A credencial anteriormente exposta precisa ser rotacionada no provedor; remover o literal não a revoga.

## Testar este projeto localmente

Na raiz principal, com o ambiente virtual ativo:

```bash
python local.py setup
python local.py admin
python local.py check
python local.py serve
```

Esses comandos usam dados fictícios em banco local separado, não os dados do cliente. Não publique a pasta principal inteira: ela contém documentação e identidade privadas. A edição destinada à revisão pública continua separada.

## Apresentação e integrações sem dados fixos no código

Configure `SITE_NAME` para o nome geral da interface. A tela de login exibe “EP Conexões - Login” e os rótulos de parceria exibem “BST”, conforme definido para o sistema. Na integração opcional de planilhas, configure `GOOGLE_SHEETS_ID` e `GOOGLE_APPLICATION_CREDENTIALS` (caminho do arquivo privado). A integração permanece um componente legado e não faz parte dos fluxos de tela validados.

Nenhuma dessas configurações deve ser preenchida em um arquivo versionado. A sanitização dos arquivos atuais não remove versões antigas de branches, PRs e histórico Git.
