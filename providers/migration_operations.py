"""Reconciliação conservadora de tabelas legadas, sem apagar ou renomear dados."""
from django.db import migrations


class CreateOrValidateLegacyModel(migrations.CreateModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.name)
        connection = schema_editor.connection
        table = model._meta.db_table
        if table not in connection.introspection.table_names():
            return super().database_forwards(app_label, schema_editor, from_state, to_state)
        if connection.vendor != 'postgresql':
            raise RuntimeError(f'Tabela legada {table} já existe. Validação automática disponível somente para PostgreSQL; nenhuma tabela será substituída.')
        with connection.cursor() as cursor:
            cursor.execute('''SELECT a.attname, format_type(a.atttypid,a.atttypmod), a.attnotnull
                              FROM pg_attribute a
                              WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped''', [table])
            columns = {name:(kind,notnull) for name,kind,notnull in cursor.fetchall()}
            constraints = connection.introspection.get_constraints(cursor,table)
        errors=[]
        def normalized(value):
            return value.replace('character varying','varchar')
        for field in model._meta.local_fields:
            actual=columns.get(field.column)
            expected=field.db_type(connection)
            if not actual or normalized(actual[0]) != normalized(expected) or actual[1] != (not field.null):
                errors.append(f'coluna incompatível: {field.column}')
                continue
            if field.primary_key and not any(c['primary_key'] and c['columns']==[field.column] for c in constraints.values()):
                errors.append(f'chave primária ausente: {field.column}')
            if field.unique and not field.primary_key and not any(c['unique'] and c['columns']==[field.column] for c in constraints.values()):
                errors.append(f'unicidade ausente: {field.column}')
            if field.is_relation and field.many_to_one:
                remote=(field.related_model._meta.db_table,field.target_field.column)
                if not any(c['columns']==[field.column] and c['foreign_key']==remote for c in constraints.values()):
                    errors.append(f'relacionamento ausente: {field.column}')
        for fields in model._meta.unique_together:
            names=[model._meta.get_field(f).column for f in fields]
            if not any(c['unique'] and c['columns']==names for c in constraints.values()):
                errors.append('restrição composta ausente: '+','.join(names))
        expected_indexes = [[model._meta.get_field(f).column for f in index.fields] for index in model._meta.indexes]
        expected_indexes += [[field.column] for field in model._meta.local_fields if field.db_index and not field.unique]
        for names in expected_indexes:
            if not any((c['index'] or c['unique']) and c['columns'][:len(names)] == names for c in constraints.values()):
                errors.append('índice ausente: '+','.join(names))
        if errors:
            raise RuntimeError(f'Migração bloqueada para preservar {table}: '+ '; '.join(errors)+'. Revise o esquema em uma restauração privada; não use --fake.')
        # Atualiza apenas o estado Django: a tabela já contém o esquema validado.

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        # Não há como deduzir se a tabela foi criada aqui ou se já era operacional.
        from django.db.migrations.exceptions import IrreversibleError
        raise IrreversibleError('A reconciliação de tabelas legadas não remove tabelas no rollback. Use o plano de retorno e backup verificado.')
