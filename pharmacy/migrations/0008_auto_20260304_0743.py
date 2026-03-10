from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('pharmacy', '0007_stockmovement'),
    ]

    operations = [
        migrations.RenameField(
            model_name='medicine',
            old_name='price',
            new_name='default_selling_price',
        ),
    ]