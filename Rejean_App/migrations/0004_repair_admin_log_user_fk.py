from django.db import migrations


def repair_admin_log_user_fk(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'django_admin_log'

    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
        stale_constraints = []
        for name, details in constraints.items():
            foreign_key = details.get('foreign_key')
            if foreign_key and foreign_key[0] == 'auth_user':
                stale_constraints.append(name)
        if not stale_constraints:
            return

        if connection.vendor != 'sqlite':
            raise RuntimeError('The admin log FK repair currently supports SQLite only.')

        log_rows = cursor.execute(
            'SELECT id, action_time, object_id, object_repr, action_flag, '
            'change_message, content_type_id, user_id FROM django_admin_log'
        ).fetchall()
        legacy_users = dict(cursor.execute('SELECT id, username FROM auth_user').fetchall())
        current_users = dict(cursor.execute(
            'SELECT username, id FROM Rejean_App_customuser'
        ).fetchall())

        repaired_rows = []
        for row in log_rows:
            user_id = row[-1]
            username = legacy_users.get(user_id)
            current_user_id = current_users.get(username)
            if current_user_id is None:
                raise RuntimeError(
                    f'Cannot remap admin log entry for legacy user id {user_id}.'
                )
            repaired_rows.append((*row[:-1], current_user_id))

        cursor.execute(
            'CREATE TABLE django_admin_log_repaired ('
            'id integer NOT NULL PRIMARY KEY AUTOINCREMENT, '
            'action_time datetime NOT NULL, '
            'object_id text NULL, '
            'object_repr varchar(200) NOT NULL, '
            'action_flag smallint unsigned NOT NULL CHECK (action_flag >= 0), '
            'change_message text NOT NULL, '
            'content_type_id integer NULL REFERENCES django_content_type(id) '
            'DEFERRABLE INITIALLY DEFERRED, '
            'user_id integer NOT NULL REFERENCES Rejean_App_customuser(id) '
            'DEFERRABLE INITIALLY DEFERRED)'
        )
        cursor.executemany(
            'INSERT INTO django_admin_log_repaired '
            '(id, action_time, object_id, object_repr, action_flag, '
            'change_message, content_type_id, user_id) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            repaired_rows,
        )
        cursor.execute('DROP TABLE django_admin_log')
        cursor.execute(
            'ALTER TABLE django_admin_log_repaired RENAME TO django_admin_log'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('Rejean_App', '0003_alter_book_availability_customuser_borrowrecord'),
        ('admin', '0003_logentry_add_action_flag_choices'),
    ]

    operations = [
        migrations.RunPython(repair_admin_log_user_fk),
    ]