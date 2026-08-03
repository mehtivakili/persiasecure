from django.db import migrations

import apps.cameras.fields


class Migration(migrations.Migration):

    dependencies = [
        ('cameras', '0002_alter_streamprofile_codec'),
    ]

    operations = [
        migrations.AlterField(
            model_name='camera',
            name='password',
            field=apps.cameras.fields.EncryptedCharField(blank=True, default='', max_length=500),
        ),
    ]
