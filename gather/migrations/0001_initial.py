# Generated by Django 5.0.6 on 2024-05-29 11:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import gather.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventSeries",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name="EventAdminGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "location",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_admin_group",
                        to="core.location",
                    ),
                ),
                ("users", models.ManyToManyField(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="EventNotifications",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reminders", models.BooleanField(default=True)),
                (
                    "location_publish",
                    models.ManyToManyField(
                        related_name="event_published", to="core.location"
                    ),
                ),
                (
                    "location_weekly",
                    models.ManyToManyField(
                        related_name="weekly_event_notifications", to="core.location"
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("start", models.DateTimeField(verbose_name="Start time")),
                ("end", models.DateTimeField(verbose_name="End time")),
                ("title", models.CharField(max_length=300)),
                (
                    "slug",
                    models.CharField(
                        help_text="This will be auto-suggested based on the event title, but feel free to customize it.",
                        max_length=60,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        help_text="Basic HTML markup is supported for your event description."
                    ),
                ),
                (
                    "image",
                    models.ImageField(upload_to=gather.models.event_img_upload_to),
                ),
                ("notifications", models.BooleanField(default=True)),
                (
                    "where",
                    models.CharField(
                        help_text="Either a specific room at this location or an address if elsewhere",
                        max_length=500,
                        verbose_name="Where will the event be held?",
                    ),
                ),
                (
                    "organizer_notes",
                    models.TextField(
                        blank=True,
                        help_text="These will only be visible to other organizers",
                        null=True,
                    ),
                ),
                (
                    "limit",
                    models.IntegerField(
                        blank=True,
                        default=0,
                        help_text="Specify a cap on the number of RSVPs, or 0 for no limit.",
                    ),
                ),
                (
                    "visibility",
                    models.CharField(
                        choices=[
                            ("public", "Public"),
                            ("private", "Private"),
                            ("community", "Community"),
                        ],
                        default="public",
                        help_text="Community events are visible only to community members. Private events are visible to those who have the link.",
                        max_length=200,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("waiting for approval", "Waiting for Approval"),
                            ("seeking feedback", "Seeking Feedback"),
                            ("ready to publish", "Ready to publish"),
                            ("live", "Live"),
                            ("canceled", "Canceled"),
                        ],
                        default="waiting for approval",
                        max_length=200,
                        verbose_name="Review Status",
                    ),
                ),
                (
                    "attendees",
                    models.ManyToManyField(
                        blank=True,
                        related_name="events_attending",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "endorsements",
                    models.ManyToManyField(
                        blank=True,
                        related_name="events_endorsed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="core.location"
                    ),
                ),
                (
                    "organizers",
                    models.ManyToManyField(
                        blank=True,
                        related_name="events_organized",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "admin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="gather.eventadmingroup",
                    ),
                ),
                (
                    "series",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="gather.eventseries",
                    ),
                ),
            ],
        ),
    ]
