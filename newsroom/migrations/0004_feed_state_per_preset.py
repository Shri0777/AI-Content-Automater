"""Keep feed state and articles per preset, since a feed can serve two.

Existing feed states are deleted first: they only save a little bandwidth,
and the next read simply fetches each feed in full once. An article is now
unique per address and preset instead of per address.
"""

from django.db import migrations, models


def forget_feed_states(apps, schema_editor):
    """Delete every saved feed state (it is rebuilt on the next read)."""
    apps.get_model("newsroom", "FeedState").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("newsroom", "0003_feeds_budgets_and_article_quality"),
    ]

    operations = [
        migrations.RunPython(forget_feed_states, migrations.RunPython.noop),
        migrations.AddField(
            model_name="feedstate",
            name="preset",
            field=models.CharField(default="", max_length=40),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="feedstate",
            name="url",
            field=models.URLField(max_length=1000),
        ),
        migrations.AlterField(
            model_name="article",
            name="url_hash",
            field=models.CharField(max_length=64),
        ),
        migrations.AddConstraint(
            model_name="article",
            constraint=models.UniqueConstraint(
                fields=("url_hash", "preset"), name="one_article_per_preset"
            ),
        ),
        migrations.AddConstraint(
            model_name="feedstate",
            constraint=models.UniqueConstraint(
                fields=("url", "preset"), name="one_state_per_feed"
            ),
        ),
    ]
