import datetime
import json
import logging

import httpx
from django.conf import settings
from django.contrib.sites.models import Site
from django.urls import reverse

from core.emails.messages import (
    admin_daily_update,
    goodbye_email,
    guest_welcome,
    guests_residents_daily_update,
)
from core.models import Location, Use

logger = logging.getLogger(__name__)


def send_guests_residents_daily_update():
    logger.info("Running task: send_guests_residents_daily_update")
    locations = Location.objects.all()
    for location in locations:
        guests_residents_daily_update(location)


def send_admin_daily_update():
    logger.info("Running task: send_admin_daily_update")
    locations = Location.objects.all()
    for location in locations:
        admin_daily_update(location)


def send_guest_welcome():
    logger.info("Running task: send_guest_welcome")
    # get all bookings WELCOME_EMAIL_DAYS_AHEAD from now.
    locations = Location.objects.all()

    # to ensure tests actually do something
    did_send_email = False

    for location in locations:
        soon = datetime.date.today() + datetime.timedelta(
            days=location.welcome_email_days_ahead
        )
        upcoming = (
            Use.objects.filter(location=location)
            .filter(arrive=soon)
            .filter(status="confirmed")
        )
        for booking in upcoming:
            guest_welcome(booking)
            did_send_email = True

    return did_send_email


def send_departure_email():
    logger.info("Running task: send_departure_email")

    # to ensure tests actually do something
    did_send_email = False

    # get all bookings departing today
    locations = Location.objects.all()
    for location in locations:
        today = datetime.date.today()
        departing = (
            Use.objects.filter(location=location)
            .filter(depart=today)
            .filter(status="confirmed")
        )
        for use in departing:
            goodbye_email(use)
            did_send_email = True

    return did_send_email


def _format_attachment(use, color):
    domain = "https://" + Site.objects.get_current().domain
    if use.user.profile.image:
        profile_img_url = domain + use.user.profile.image.url
    else:
        profile_img_url = domain + "/static/img/default.jpg"
    booking_url = "<{}{}|{} - {} in {}>\n{}".format(
        domain,
        use.booking.get_absolute_url(),
        use.arrive.strftime("%B %d"),
        use.depart.strftime("%B %d"),
        use.resource.name,
        use.user.profile.bio,
    )
    profile_url = (domain + reverse("user_detail", args=(use.user.username,)),)
    item = {
        "color": color,
        "fallback": use.user.get_full_name(),
        "title": use.user.get_full_name(),
        "title_link": profile_url[0],
        "text": booking_url,
        "thumb_url": profile_img_url,
    }
    return item


def slack_embassysf_daily():
    """post daily arrivals and departures to slack. to enable, add an incoming
    web hook to the specific channel you want this to post to. grab the webhook
    url and put it in the webhook variable below."""
    if not settings.ENABLE_SLACK:
        logger.info("Skipping task: slack_embassysf_daily")
        return

    logger.info("Running task: slack_embassysf_daily")
    webhook = (
        "https://hooks.slack.com/services/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"
    )
    today = datetime.date.today()
    location = Location.objects.get(slug="embassysf")
    arriving_today = (
        Use.objects.filter(location=location)
        .filter(arrive=today)
        .filter(status="confirmed")
    )
    departing_today = (
        Use.objects.filter(location=location)
        .filter(depart=today)
        .filter(status="confirmed")
    )

    payload = {
        "text": "Arrivals and Departures for {}".format(today.strftime("%B %d, %Y")),
        "attachments": [],
    }
    for a in arriving_today:
        item = _format_attachment(a, "good")
        payload["attachments"].append(item)
    for d in departing_today:
        item = _format_attachment(d, "danger")
        payload["attachments"].append(item)
    if len(arriving_today) == 0 and len(departing_today) == 0:
        payload["attachments"].append(
            {
                "fallback": "No arrivals or departures today",
                "text": "No arrivals or departures today",
            }
        )

    js = json.dumps(payload)
    logger.debug(js)
    resp = httpx.post(webhook, data=js)
    logger.debug(f"Slack response: {resp.text}")
