import logging
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib.sites.models import Site
from django.urls import reverse

from core.models import Payment

logger = logging.getLogger(__name__)


class PaymentException(Exception):
    pass


def _charge_description(booking):
    booking_url = "https://" + Site.objects.get_current().domain
    booking_url += reverse(
        "booking_detail", args=(booking.use.location.slug, booking.id)
    )
    descr = f"{booking.use.user.get_full_name()} from {str(booking.use.arrive)} - "
    descr += f"{str(booking.use.depart)}. Details: {booking_url}."
    return descr


def charge_short_term_membership(user):
    amount_owed_cents = settings.SHORT_TERM_MEMBERSHIP_COST * 100
    return_url = f"{settings.CANONICAL_URL}/people/{user.username}/"

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.PaymentIntent.create(
        amount=amount_owed_cents,
        currency="usd",
        customer=user.profile.stripe_customer_id,
        payment_method=user.profile.stripe_payment_method_id,
        description="Short-term Membership",
        confirm=True,
        return_url=return_url,
    )


def charge_booking(booking):
    logger.debug(f"stripe_charge_booking(booking={booking.id})")

    # stripe will raise a stripe.CardError if the charge fails. this
    # function purposefully does not handle that error so the calling
    # function can decide what to do.
    descr = _charge_description(booking)

    amt_owed = booking.bill.total_owed()
    amt_owed_cents = int(amt_owed * 100)
    return_url = f"{settings.CANONICAL_URL}/people/{booking.use.user.username}/"

    stripe.api_key = settings.STRIPE_SECRET_KEY
    charge = stripe.PaymentIntent.create(
        amount=amt_owed_cents,
        currency="usd",
        customer=booking.use.user.profile.stripe_customer_id,
        payment_method=booking.use.user.profile.stripe_payment_method_id,
        description=descr,
        confirm=True,
        return_url=return_url,
    )

    # Create a Payment object to record the charge
    return Payment.objects.create(
        bill=booking.bill,
        user=booking.use.user,
        payment_service="Stripe",
        payment_method=booking.use.user.profile.stripe_payment_method_id,
        paid_amount=amt_owed,
        transaction_id=charge.id,
    )


def charge_user(user, bill, amount_dollars, reference):
    logger.debug(f"stripe_charge_user({user}, {bill}, {amount_dollars}, {reference})")

    # stripe will raise a stripe.CardError if the charge fails. this
    # function purposefully does not handle that error so the calling
    # function can decide what to do.

    amt_cents = int(amount_dollars * 100)
    stripe.api_key = settings.STRIPE_SECRET_KEY
    charge = stripe.Charge.create(
        amount=amt_cents,
        currency="usd",
        customer=user.profile.stripe_customer_id,
        description=reference,
    )

    # Store the charge details in a Payment object
    return Payment.objects.create(
        bill=bill,
        user=user,
        payment_service="Stripe",
        payment_method=charge.source.brand,
        paid_amount=amount_dollars,
        transaction_id=charge.id,
    )


def issue_refund(payment, amount=None):
    logger.debug(f"stripe_issue_refund(payment={payment.id})")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    charge = stripe.Charge.retrieve(payment.transaction_id)
    logger.debug("refunding amount")
    logger.debug(amount)
    if amount:
        # amount refunded has to be given in cents
        refund_amount_cents = int(float(amount) * 100)
        logger.debug(refund_amount_cents)
        refund = charge.refund(amount=refund_amount_cents)
    else:
        refund = charge.refund()

    # Store the charge details in a Payment object
    return Payment.objects.create(
        bill=payment.bill,
        user=payment.user,
        payment_service="Stripe",
        payment_method="Refund",
        paid_amount=-1 * Decimal(amount),
        transaction_id=refund.id,
    )


def stripe_charge_card_third_party(booking, amount, token, charge_descr):
    logger.debug(f"stripe_charge_card_third_party(booking={booking.id})")
    logger.debug("in charge card 3rd party")

    # stripe will raise a stripe.CardError if the charge fails. this
    # function purposefully does not handle that error so the calling
    # function can decide what to do.
    descr = _charge_description(booking)
    descr += charge_descr

    amt_owed_cents = int(amount * 100)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    charge = stripe.Charge.create(
        amount=amt_owed_cents,
        currency="usd",
        card=token,
        description=descr,
    )
    return charge
