import contextlib
import datetime
import logging
import time
from decimal import Decimal

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from stripe.error import CardError

from core import payment_gateway
from core.decorators import house_admin_required, resident_or_admin_required
from core.emails.messages import (
    send_booking_receipt,
    send_from_location_address,
)
from core.forms import PaymentForm
from core.models import (
    Bill,
    BillLineItem,
    Booking,
    Location,
    LocationFee,
    Payment,
)
from core.tasks import guest_welcome
from core.views import occupancy

logger = logging.getLogger(__name__)


@require_POST
@login_required
def create_checkout_session(request, username):
    # check permissions
    user = get_object_or_404(User, username=username)
    if request.user != user:
        messages.info(
            request,
            (
                "You are not authorized to add a credit card to this page. "
                "Please log in or use the 3rd party."
            ),
        )
        return HttpResponseRedirect("/404")

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # check if user exists on stripe
        if user.profile.stripe_customer_id:
            customer = stripe.Customer.retrieve(user.profile.stripe_customer_id)
        else:
            customer = stripe.Customer.create(
                email=user.email, name=f"{user.first_name} {user.last_name}"
            )
            user.profile.stripe_customer_id = customer.id
            user.profile.save()

        success_url = (
            f"{settings.CANONICAL_URL}/people/{user.username}/checkout-success/"
            "?session_id={CHECKOUT_SESSION_ID}"  # this {CHECKOUT_SESSION_ID} is for stripe
        )
        checkout_session = stripe.checkout.Session.create(
            mode="setup",
            currency="usd",
            customer=customer.id,
            success_url=success_url,
            cancel_url=f"{settings.CANONICAL_URL}/people/{user.username}/",
        )
    except Exception as e:
        messages.info(
            request,
            (
                '<span class="text-danger">Drat, '
                f"there was a problem with our payment processor: <em>{e}</em></span>"
            ),
        )
        return redirect("user_detail", user.username)

    # response
    response = HttpResponseRedirect(checkout_session.url)
    response.status_code = 303
    return response


@login_required
def checkout_success(request, username):
    # check permissions
    user = get_object_or_404(User, username=username)
    if request.user != user:
        messages.info(
            request,
            (
                "You are not authorized to add a credit card to this page. "
                "Please log in or use the 3rd party."
            ),
        )
        return HttpResponseRedirect("/404")

    stripe_session_id = request.GET.get("session_id")
    if not stripe_session_id:
        message = "Could not get Stripe Session ID"
        messages.error(request, message)
        raise Exception(message)

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe_session = stripe.checkout.Session.retrieve(
        stripe_session_id, expand=["setup_intent"]
    )

    # save payment method on user
    stripe_payment_method_id = stripe_session.setup_intent.payment_method
    user.profile.stripe_payment_method_id = stripe_payment_method_id
    user.profile.save()

    # set default payment source to customer in stripe
    stripe.Customer.modify(
        user.profile.stripe_customer_id,
        invoice_settings={"default_payment_method": stripe_payment_method_id},
    )

    messages.info(request, "Thanks! Your card has been saved.")
    return HttpResponseRedirect(f"/people/{user.username}")


@login_required
def user_delete_card(request, username):
    # check permissions
    user = get_object_or_404(User, username=username)
    if request.user != user:
        messages.info(
            request,
            "You are not authorized to change this. Please log in or use the 3rd party.",
        )
        return HttpResponseRedirect("/404")

    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.Customer.delete(user.profile.stripe_customer_id)
    except Exception as e:
        messages.info(
            request,
            (
                '<span class="text-danger">Drat, '
                f"there was a problem with our payment processor: <em>{e}</em></span>"
            ),
        )
        return redirect("user_detail", user.username)

    user.profile.stripe_customer_id = None
    user.profile.save()

    messages.info(request, "Card deleted.")
    return HttpResponseRedirect(f"/people/{user.username}")


@house_admin_required
def ManagePayment(request, location_slug, bill_id):
    if request.method != "POST":
        return HttpResponseRedirect("/404")
    get_object_or_404(Location, slug=location_slug)
    bill = get_object_or_404(Bill, id=bill_id)

    logger.debug(request.POST)
    action = request.POST.get("action")
    if action == "Submit":
        # process a refund
        payment_id = request.POST.get("payment_id")
        payment = get_object_or_404(Payment, id=payment_id)
        refund_amount = request.POST.get("refund-amount")
        logger.debug(refund_amount)
        logger.debug(payment.net_paid())
        if Decimal(refund_amount) > Decimal(payment.net_paid()):
            messages.add_message(
                request, messages.INFO, "Cannot refund more than payment balance"
            )
        else:
            payment_gateway.issue_refund(payment, refund_amount)
            if bill.is_booking_bill():
                messages.add_message(
                    request,
                    messages.INFO,
                    "A refund for $%d was applied." % (Decimal(refund_amount)),
                )
            else:
                raise Exception("not a booking bill or any other type")
    elif action == "Save":
        logger.debug("saving record of external payment")
        # record a manual payment
        payment_method = request.POST.get("payment_method").strip().title()
        paid_amount = request.POST.get("paid_amount").strip()
        # JKS we store user = None for cash payments since we don't know for
        # certain *who* it was that made the payment. in the future, we could
        # allow admins to enter who made the payment, if desired.
        Payment.objects.create(
            payment_method=payment_method,
            paid_amount=paid_amount,
            bill=bill,
            user=None,
            transaction_id="Manual",
        )
        if bill.is_booking_bill():
            messages.add_message(request, messages.INFO, "Manual payment recorded")
        else:
            raise Exception("not a booking bill or any other type")

    # JKS this is a little inelegant as it assumes that this page will always
    # a) want to redirect to a manage page and b) that there are only two types
    # of bills. this should be abstracted at some point.
    if bill.is_booking_bill():
        return HttpResponseRedirect(
            reverse("booking_manage", args=(location_slug, bill.bookingbill.booking.id))
        )
    else:
        raise Exception("not a booking bill or any other type")


@house_admin_required
def RecalculateBill(request, location_slug, bill_id):
    if request.method != "POST":
        return HttpResponseRedirect("/404")
    location = get_object_or_404(Location, slug=location_slug)
    bill = get_object_or_404(Bill, id=bill_id)

    # what kind of bill is this?
    if bill.is_booking_bill():
        booking = bill.bookingbill.booking
        reset_suppressed = request.POST.get("reset_suppressed")
        if reset_suppressed == "true":
            booking.generate_bill(reset_suppressed=True)
        else:
            booking.generate_bill()
        messages.add_message(request, messages.INFO, "The bill has been recalculated.")
        return HttpResponseRedirect(
            reverse("booking_manage", args=(location.slug, booking.id))
        )
    else:
        raise Exception("Unrecognized bill object")


@house_admin_required
def DeleteBillLineItem(request, location_slug, bill_id):
    if request.method != "POST":
        return HttpResponseRedirect("/404")
    location = get_object_or_404(Location, slug=location_slug)
    bill = get_object_or_404(Bill, pk=bill_id)

    if bill.is_booking_bill():
        booking = bill.bookingbill.booking
        logger.debug("in delete bill line item")
        logger.debug(request.POST)
        item_id = int(request.POST.get("payment_id"))
        line_item = BillLineItem.objects.get(id=item_id)
        line_item.delete()
        if line_item.fee:
            booking.suppress_fee(line_item)
        booking.generate_bill()
        messages.add_message(request, messages.INFO, "The line item was deleted.")
        return HttpResponseRedirect(
            reverse("booking_manage", args=(location.slug, booking.id))
        )
    else:
        raise Exception("Unrecognized bill object")


@house_admin_required
def BillCharge(request, location_slug, bill_id):
    if request.method != "POST":
        return HttpResponseRedirect("/404")
    location = get_object_or_404(Location, slug=location_slug)
    bill = get_object_or_404(Bill, pk=bill_id)

    logger.debug(request.POST)
    # how much to charge?
    charge_amount_dollars = Decimal(request.POST.get("charge-amount"))
    logger.debug("request to charge user $%d" % charge_amount_dollars)
    if charge_amount_dollars > bill.total_owed():
        messages.add_message(
            request,
            messages.INFO,
            "Cannot charge more than remaining amount owed ($%d was requested on $%d owed)"
            % (charge_amount_dollars, bill.total_owed()),
        )
        raise Exception(
            "bill charge error: cannot charge more than remaining amount owed"
        )

    if bill.is_booking_bill():
        user = bill.bookingbill.booking.user
        reference = "%d booking ref#%d" % (location.name, bill.bookingbill.booking.id)
    else:
        raise Exception("Unknown bill type. Cannot determine user.")

    try:
        payment_gateway.charge_user(user, bill, charge_amount_dollars, reference)
    except CardError as e:
        messages.add_message(
            request, messages.INFO, f"Charge failed with the following error: {e}"
        )
        if bill.is_booking_bill():
            return HttpResponseRedirect(
                reverse(
                    "booking_manage", args=(location_slug, bill.bookingbill.booking.id)
                )
            )
        else:
            raise Exception("bill is of unknown type") from e

    if bill.is_booking_bill():
        messages.add_message(request, messages.INFO, "The card was charged.")
        return HttpResponseRedirect(
            reverse("booking_manage", args=(location_slug, bill.bookingbill.booking.id))
        )
    else:
        raise Exception("bill is of unknown type")


@house_admin_required
def AddBillLineItem(request, location_slug, bill_id):
    # can be used to apply a discount or a one time charge for, for example, a
    # cleaning fee.
    if request.method != "POST":
        return HttpResponseRedirect("/404")
    location = get_object_or_404(Location, slug=location_slug)
    bill = get_object_or_404(Bill, pk=bill_id)

    reason = request.POST.get("reason")
    calculation_type = request.POST.get("calculation_type")
    line_item_type = "discount" if request.POST.get("discount") else "fee"
    if line_item_type == "discount":
        if calculation_type == "absolute":
            reason = "Discount: " + reason
            amount = -Decimal(request.POST.get("discount"))
        elif calculation_type == "percent":
            percent = Decimal(request.POST.get("discount")) / 100
            reason = f"Discount ({percent * Decimal(100.0)}%): {reason}"
            if percent < 0.0 or percent > 100.0:
                messages.add_message(
                    request, messages.INFO, "Invalid percent value given."
                )
                return HttpResponseRedirect(
                    reverse(
                        "booking_manage",
                        args=(location.slug, bill.bookingbill.booking.id),
                    )
                )
            amount = -(bill.subtotal_amount() * percent)
        else:
            messages.add_message(request, messages.INFO, "Invalid discount type.")
            return HttpResponseRedirect(
                reverse(
                    "booking_manage", args=(location.slug, bill.bookingbill.booking.id)
                )
            )
    else:
        # then it's a fee
        if calculation_type == "absolute":
            reason = "Fee: " + reason
            amount = float(request.POST.get("extra_fee"))
        elif calculation_type == "percent":
            percent = Decimal(request.POST.get("extra_fee")) / 100
            reason = f"Fee ({percent * Decimal(100.0)}%): {reason}"
            if percent < 0.0 or percent > 100.0:
                messages.add_message(
                    request, messages.INFO, "Invalid percent value given."
                )
                return HttpResponseRedirect(
                    reverse(
                        "booking_manage",
                        args=(location.slug, bill.bookingbill.booking.id),
                    )
                )
            amount = bill.subtotal_amount() * percent
        else:
            messages.add_message(request, messages.INFO, "Invalid fee type.")
            return HttpResponseRedirect(
                reverse(
                    "booking_manage", args=(location.slug, bill.bookingbill.booking.id)
                )
            )

    new_line_item = BillLineItem(
        description=reason, amount=amount, paid_by_house=False, custom=True
    )
    new_line_item.bill = bill
    new_line_item.save()
    # regenerate the bill now that we've applied some new fees (even if the
    # rate has not changed, other percentage-based fees may be affected by this
    # new line item)
    if bill.is_booking_bill():
        booking = bill.bookingbill.booking
        booking.generate_bill()
        messages.add_message(request, messages.INFO, f"The {line_item_type} was added.")
        return HttpResponseRedirect(
            reverse("booking_manage", args=(location.slug, booking.id))
        )
    else:
        raise Exception("Unrecognized bill object")


def _assemble_and_send_email(location_slug, post):
    # This is the code path for sending an email from the admin booking page
    location = get_object_or_404(Location, slug=location_slug)
    subject = post.get("subject")
    recipient = post.get("recipient")
    body = post.get("body") + "\n\n" + post.get("footer")
    # TODO - This isn't fully implemented yet -JLS
    send_from_location_address(subject, body, None, recipient, location)


@resident_or_admin_required
def payments_today(request, location_slug):
    today = timezone.localtime(timezone.now())
    return HttpResponseRedirect(
        reverse(
            "location_payments",
            args=[],
            kwargs={
                "location_slug": location_slug,
                "year": today.year,
                "month": today.month,
            },
        )
    )


@login_required
def PeopleDaterangeQuery(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    start_str = request.POST.get("start_date")
    end_str = request.POST.get("end_date")
    s_month, s_day, s_year = start_str.split("/")
    e_month, e_day, e_year = end_str.split("/")
    start_date = datetime.date(int(s_year), int(s_month), int(s_day))
    end_date = datetime.date(int(e_year), int(e_month), int(e_day))
    bookings_for_daterange = (
        Booking.objects.filter(Q(status="confirmed"))
        .exclude(depart__lt=start_date)
        .exclude(arrive__gte=end_date)
    )
    recipients = []
    for r in bookings_for_daterange:
        recipients.append(r.user)
    residents = location.residents()
    recipients = recipients + list(residents)
    html = "<div class='btn btn-info disabled' id='recipient-list'>Your message will go to these people: "
    for person in recipients:
        info = (
            "<a class='link-light-color' href='/people/"
            + person.username
            + "'>"
            + person.first_name
            + " "
            + person.last_name
            + "</a>, "
        )
        html += info

    html = html.strip(", ")


def submit_payment(request, booking_uuid, location_slug):
    booking = Booking.objects.get(uuid=booking_uuid)
    location = get_object_or_404(Location, slug=location_slug)
    if request.method == "POST":
        form = PaymentForm(request.POST, default_amount=None)
        if form.is_valid():
            # account secret key
            stripe.api_key = settings.STRIPE_SECRET_KEY

            # get the payment details from the form
            token = request.POST.get("stripeToken")
            amount = float(request.POST.get("amount"))
            pay_name = request.POST.get("name")
            pay_email = request.POST.get("email")
            comment = request.POST.get("comment")

            pay_user = None
            with contextlib.suppress(Exception):
                pay_user = User.objects.filter(email=pay_email).first()

            # create the charge on Stripe's servers - this will charge the user's card
            charge_descr = f"payment from {pay_name} ({pay_email})."
            if comment:
                charge_descr += f" Comment added: {comment}"
            try:
                charge = payment_gateway.stripe_charge_card_third_party(
                    booking, amount, token, charge_descr
                )

                # associate payment information with booking
                Payment.objects.create(
                    bill=booking.bill,
                    user=pay_user,
                    payment_service="Stripe",
                    payment_method=charge.source.brand,
                    paid_amount=(charge.amount / 100.00),
                    transaction_id=charge.id,
                )

                if booking.bill.total_owed() <= 0.0:
                    # if the booking is all paid up, do All the Things to confirm.
                    booking.confirm()
                    send_booking_receipt(booking, send_to=pay_email)

                    # XXX TODO need a way to check if this has already been sent :/
                    days_until_arrival = (
                        booking.use.arrive - datetime.date.today()
                    ).days
                    if (
                        days_until_arrival
                        <= booking.use.location.welcome_email_days_ahead
                    ):
                        guest_welcome(booking.use)
                    messages.add_message(
                        request,
                        messages.INFO,
                        f"Thanks you for your payment! A receipt is being emailed to you at {pay_email}",
                    )
                else:
                    messages.add_message(
                        request,
                        messages.INFO,
                        f"Thanks you for your payment! There is now a pending amount due of ${booking.bill.total_owed():.2f}",
                    )
                    form = PaymentForm(default_amount=booking.bill.total_owed)

            except Exception as e:
                messages.add_message(
                    request,
                    messages.INFO,
                    "Drat, there was a problem with your card. Sometimes this reflects a card transaction limit, or bank "
                    + "hold due to an unusual charge. Please contact your bank or credit card, or try a different card. The "
                    + f"error returned was: <em>{e}</em>",
                )
        else:
            logger.debug("payment form not valid")
            logger.debug(form.errors)

    else:
        form = PaymentForm(default_amount=booking.bill.total_owed)

    owed_color = "text-danger" if booking.bill.total_owed() > 0.0 else "text-success"
    return render(
        request,
        "payment.html",
        {
            "r": booking,
            "location": location,
            "total_owed_color": owed_color,
            "form": form,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        },
    )


@resident_or_admin_required
def payments(request, location_slug, year, month):
    t0 = time.time()
    logger.debug("payments: timing begun:")
    location = get_object_or_404(Location, slug=location_slug)
    start, end, next_month, prev_month, month, year = occupancy.get_calendar_dates(
        month, year
    )

    summary_totals = {
        "gross_rent": 0,
        "net_rent_resident": 0,
        "gross_rent_transient": 0,
        "net_rent_transient": 0,
        "hotel_tax": 0,
        "hotel_tax_percent": 0.0,
        "res_external_txs_paid": 0,
        "res_external_txs_fees": 0,
        "sub_external_txs_paid": 0,
        "sub_external_txs_fees": 0,
    }

    ##############################

    booking_totals = {
        "count": 0,
        "house_fees": 0,
        "to_house": 0,
        "non_house_fees": 0,
        "paid_amount": 0,
    }

    # JKS if the booking has bill line items that are not paid by the house
    # (so-called non_house_fees), then the amount to_house counts as transient
    # occupancy income. otherwise it counts as resident occupancy income.
    # TODO: we're essentially equating non house fees with hotel taxes. we
    # should make this explicit in some way.

    booking_payments_this_month = (
        Payment.objects.booking_payments_by_location(location)
        .filter(payment_date__gte=start, payment_date__lte=end)
        .order_by("payment_date")
        .reverse()
    )
    for p in booking_payments_this_month:
        # pull out the values we call multiple times to make this faster
        p_to_house = p.to_house()
        p_bill_non_house_fees = p.bill.non_house_fees()
        p_house_fees = p.house_fees()
        p_non_house_fees = p.non_house_fees()
        p_paid_amount = p.paid_amount

        summary_totals["gross_rent"] += p_to_house
        if p_bill_non_house_fees > 0:
            summary_totals["gross_rent_transient"] += p_to_house + p_house_fees
            summary_totals["net_rent_transient"] += p_to_house
            # XXX is p_non_house_fees == p_bill_non_house_fees??
            summary_totals["hotel_tax"] += p_non_house_fees
        else:
            summary_totals["net_rent_resident"] += p_to_house
        # track booking totals
        booking_totals["count"] = booking_totals["count"] + 1
        booking_totals["to_house"] = booking_totals["to_house"] + p_to_house
        booking_totals["non_house_fees"] = (
            booking_totals["non_house_fees"] + p_non_house_fees
        )
        booking_totals["house_fees"] = booking_totals["house_fees"] + p_house_fees
        booking_totals["paid_amount"] = booking_totals["paid_amount"] + p_paid_amount
        if p.transaction_id == "Manual":
            summary_totals["res_external_txs_paid"] += p_paid_amount
            summary_totals["res_external_txs_fees"] += p_house_fees

    not_paid_by_house = LocationFee.objects.filter(location=location).filter(
        fee__paid_by_house=False
    )
    for loc_fee in not_paid_by_house:
        summary_totals["hotel_tax_percent"] += loc_fee.fee.percentage * 100

    ##############################

    summary_totals["res_total_transfer"] = (
        summary_totals["gross_rent"]
        + summary_totals["hotel_tax"]
        - summary_totals["res_external_txs_paid"]
        - summary_totals["res_external_txs_fees"]
    )

    summary_totals["total_transfer"] = summary_totals["res_total_transfer"]
    summary_totals["gross_bookings"] = (
        summary_totals["gross_rent_transient"] + summary_totals["net_rent_resident"]
    )

    t1 = time.time()
    dt = t1 - t0
    logger.debug("payments: timing ended. time taken:")
    logger.debug(dt)
    return render(
        request,
        "payments.html",
        {
            "booking_payments": booking_payments_this_month,
            "summary_totals": summary_totals,
            "booking_totals": booking_totals,
            "location": location,
            "this_month": start,
            "previous_date": prev_month,
            "next_date": next_month,
        },
    )
