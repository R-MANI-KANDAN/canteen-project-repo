# Description: Razorpay webhook handler with signature verification and event processing.
import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Payment, WebhookLog
from .services import verify_webhook_signature

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook_handler(request):
    """
    Main Razorpay webhook endpoint.

    1. Verifies webhook signature using WEBHOOK_SECRET
    2. Checks idempotency (skip already-processed events)
    3. Logs to WebhookLog model
    4. Routes to event-specific handlers
    5. Returns 200 OK quickly

    Razorpay retries webhooks for up to 24 hours on non-2xx responses.
    """
    # Get raw body and signature
    request_body = request.body.decode('utf-8')
    signature = request.headers.get('X-Razorpay-Signature', '')
    event_id = request.headers.get('X-Razorpay-Event-Id', '')

    if not signature:
        logger.warning("Webhook received without signature header")
        return JsonResponse({'status': 'error', 'message': 'Missing signature'}, status=400)

    # Verify signature
    is_valid = verify_webhook_signature(request_body, signature)

    # Parse payload
    try:
        payload = json.loads(request_body)
    except json.JSONDecodeError:
        logger.error("Webhook received with invalid JSON body")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    event_type = payload.get('event', 'unknown')

    # Extract IDs from payload for logging
    razorpay_order_id = ''
    razorpay_payment_id = ''
    if 'payment' in payload.get('payload', {}):
        entity = payload['payload']['payment'].get('entity', {})
        razorpay_payment_id = entity.get('id', '')
        razorpay_order_id = entity.get('order_id', '')
    elif 'order' in payload.get('payload', {}):
        entity = payload['payload']['order'].get('entity', {})
        razorpay_order_id = entity.get('id', '')

    # Use event_id for idempotency, fall back to generated ID
    if not event_id:
        event_id = f"{event_type}_{razorpay_payment_id}_{razorpay_order_id}"

    # Check idempotency — skip already-processed events
    existing_log = WebhookLog.objects.filter(event_id=event_id).first()
    if existing_log and existing_log.is_processed:
        logger.info(f"Webhook already processed: {event_id}")
        return JsonResponse({'status': 'ok', 'message': 'Already processed'})

    # Create or update webhook log
    webhook_log, created = WebhookLog.objects.update_or_create(
        event_id=event_id,
        defaults={
            'event_type': event_type,
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'payload': payload,
            'is_verified': is_valid,
        }
    )

    if not is_valid:
        webhook_log.error_message = 'Signature verification failed'
        webhook_log.save()
        logger.warning(f"Webhook signature invalid for event {event_id}")
        return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)

    # Route to event-specific handler
    try:
        if event_type == 'payment.authorized':
            handle_payment_authorized(payload)
        elif event_type == 'payment.captured':
            handle_payment_captured(payload)
        elif event_type == 'payment.failed':
            handle_payment_failed(payload)
        elif event_type == 'order.paid':
            handle_order_paid(payload)
        elif event_type == 'refund.created':
            handle_refund_created(payload)
        elif event_type == 'refund.processed':
            handle_refund_processed(payload)
        else:
            logger.info(f"Unhandled webhook event: {event_type}")

        webhook_log.is_processed = True
        webhook_log.save()

    except Exception as e:
        webhook_log.error_message = str(e)
        webhook_log.save()
        logger.error(f"Webhook processing error for {event_id}: {e}")
        # Still return 200 to prevent retries for processing errors
        # (the data is logged and can be reprocessed manually)

    return JsonResponse({'status': 'ok'})


def handle_payment_authorized(payload):
    """Handles payment.authorized — payment is authorized, pending capture."""
    entity = payload['payload']['payment']['entity']
    payment_id = entity.get('id', '')
    order_id = entity.get('order_id', '')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        if payment.status not in ('captured',):  # Don't downgrade status
            payment.status = 'authorized'
            payment.razorpay_payment_id = payment_id
            payment.webhook_received = True
            payment.webhook_event = 'payment.authorized'
            payment.save()
            logger.info(f"Payment authorized via webhook: {payment_id}")
    except Payment.DoesNotExist:
        logger.warning(f"Webhook: Payment not found for order {order_id}")


def handle_payment_captured(payload):
    """
    Handles payment.captured — payment successfully captured.
    This is the critical webhook for confirming payments.
    """
    entity = payload['payload']['payment']['entity']
    payment_id = entity.get('id', '')
    order_id = entity.get('order_id', '')
    method = entity.get('method', 'other')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        payment.status = 'captured'
        payment.razorpay_payment_id = payment_id
        payment.webhook_received = True
        payment.webhook_event = 'payment.captured'

        # Update payment method from webhook data
        method_map = dict(Payment.PAYMENT_METHOD_CHOICES)
        if method in method_map:
            payment.payment_method = method

        # If not already verified by the frontend flow, process now
        if not payment.is_verified:
            from .services import process_successful_payment
            process_successful_payment(payment, {
                'razorpay_payment_id': payment_id,
                'razorpay_signature': '',  # Not available in webhooks
            })
        else:
            payment.save()

        logger.info(f"Payment captured via webhook: {payment_id}")
    except Payment.DoesNotExist:
        logger.warning(f"Webhook: Payment not found for order {order_id}")


def handle_payment_failed(payload):
    """Handles payment.failed — payment attempt failed."""
    entity = payload['payload']['payment']['entity']
    payment_id = entity.get('id', '')
    order_id = entity.get('order_id', '')
    error_desc = entity.get('error_description', 'Payment failed')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        if payment.status != 'captured':  # Don't override successful payments
            payment.status = 'failed'
            payment.razorpay_payment_id = payment_id
            payment.webhook_received = True
            payment.webhook_event = 'payment.failed'
            payment.remarks = error_desc
            payment.save()
            logger.info(f"Payment failed via webhook: {payment_id} — {error_desc}")
    except Payment.DoesNotExist:
        logger.warning(f"Webhook: Payment not found for order {order_id}")


def handle_order_paid(payload):
    """Handles order.paid — order is fully paid. Double verification."""
    order_entity = payload['payload']['order']['entity']
    order_id = order_entity.get('id', '')

    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        if payment.status != 'captured':
            payment.status = 'captured'
            payment.webhook_received = True
            payment.webhook_event = 'order.paid'
            payment.save()
            logger.info(f"Order paid confirmed via webhook: {order_id}")
    except Payment.DoesNotExist:
        logger.warning(f"Webhook: Payment not found for order {order_id}")


def handle_refund_created(payload):
    """Handles refund.created — refund initiated."""
    entity = payload['payload']['refund']['entity'] if 'refund' in payload.get('payload', {}) else {}
    payment_id = entity.get('payment_id', '')

    try:
        payment = Payment.objects.get(razorpay_payment_id=payment_id)
        payment.webhook_event = 'refund.created'
        payment.remarks = f"Refund initiated: {entity.get('id', '')}"
        payment.save()
        logger.info(f"Refund created for payment: {payment_id}")
    except Payment.DoesNotExist:
        logger.warning(f"Webhook: Payment not found for refund on {payment_id}")


def handle_refund_processed(payload):
    """Handles refund.processed — refund completed."""
    entity = payload['payload']['refund']['entity'] if 'refund' in payload.get('payload', {}) else {}
    payment_id = entity.get('payment_id', '')

    try:
        payment = Payment.objects.get(razorpay_payment_id=payment_id)
        payment.status = 'refunded'
        payment.webhook_event = 'refund.processed'
        payment.remarks = f"Refund processed: {entity.get('id', '')}"
        payment.save()
        logger.info(f"Refund processed for payment: {payment_id}")
    except Payment.DoesNotExist:
        logger.warning(f"Webhook: Payment not found for refund on {payment_id}")
