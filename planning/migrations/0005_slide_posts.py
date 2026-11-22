"""Slide posts: AI artwork becomes opt-in, plans get a brand colour, and the
review gains a sixth score (shareability), so totals run to 30 instead of 25.

Existing plans keep the same bar for automatic posting: their minimum is
scaled from "out of 25" to "out of 30" (22 becomes 26, 25 becomes 30).
"""

from django.db import migrations, models


def scale_minimums_to_thirty(apps, schema_editor):
    """Scale each plan's auto_post_min_score from out of 25 to out of 30."""
    ContentPlan = apps.get_model("planning", "ContentPlan")
    for plan in ContentPlan.objects.all():
        plan.auto_post_min_score = round(plan.auto_post_min_score * 30 / 25)
        plan.save(update_fields=["auto_post_min_score"])


def scale_minimums_to_twenty_five(apps, schema_editor):
    """Undo scale_minimums_to_thirty."""
    ContentPlan = apps.get_model("planning", "ContentPlan")
    for plan in ContentPlan.objects.all():
        plan.auto_post_min_score = round(plan.auto_post_min_score * 25 / 30)
        plan.save(update_fields=["auto_post_min_score"])


class Migration(migrations.Migration):
    dependencies = [
        ("planning", "0004_custom_topics"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentplan",
            name="ai_artwork_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="contentplan",
            name="brand_colour",
            field=models.CharField(default="#0E1634", max_length=7),
        ),
        migrations.AlterField(
            model_name="contentplan",
            name="auto_post_min_score",
            field=models.PositiveIntegerField(default=26),
        ),
        migrations.RunPython(scale_minimums_to_thirty, scale_minimums_to_twenty_five),
    ]
