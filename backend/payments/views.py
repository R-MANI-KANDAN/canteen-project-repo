# Description: View functions for Razorpay payment checkout, verification, and result pages.
import json
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.conf import settings

from base.models import Product, Order
from .models import Payment
from .services import (
    create_razorpay_order, verify_payment_signature,
    process_successful_payment, calculate_pickup_slot,
)
from .utils import generate_receipt_pdf, generate_invoice_number, generate_qr_code

logger = logging.getLogger(__name__)


@login_required
def checkout_view(request):
    """
    Renders the enhanced checkout page with Razorpay integration.
    Cart data comes from localStorage (sent by frontend JS).
    """
    pickup_slot, _ = calculate_pickup_slot()
    context = {
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'pickup_slot': pickup_slot,
        'user': request.user,
    }
    return render(request, 'payments/checkout.html', context)


@login_required
@require_POST
def create_order_api(request):
    """
    AJAX endpoint: Creates Order rows in DB + Razorpay order.

    Receives JSON:
    {
        "items": [{"id": 1, "name": "Dosa", "qty": 2, "price": 40}, ...],
        "pickup_time": "12:45",
        "order_type": "Dine In",
        "date": "2026-06-26",
        "total": 120
    }

    Returns JSON:
    {
        "status": "success",
        "order_id": "order_xxxxx",
        "amount": 12000,
        "currency": "INR",
        "key_id": "rzp_test_xxxxx",
        "order_ref": "LCT-0001",
        "order_ids": [1, 2, 3]
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    items = data.get('items', [])
    pickup_time = data.get('pickup_time', '')
    order_type = data.get('order_type', 'Dine In')
    date_str = data.get('date', '')
    total = Decimal(str(data.get('total', 0)))

    if not items:
        return JsonResponse({'status': 'error', 'message': 'Cart is empty'}, status=400)

    if total <= 0:
        return JsonResponse({'status': 'error', 'message': 'Invalid amount'}, status=400)

    # Validate total against actual product prices
    import datetime
    try:
        order_date = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        order_date = datetime.date.today()

    # Verify prices server-side to prevent tampering
    server_total = Decimal('0')
    validated_items = []
    for item in items:
        try:
            product = Product.objects.get(pk=item.get('id'))
        except Product.DoesNotExist:
            return JsonResponse(
                {'status': 'error', 'message': f"Product {item.get('id')} not found"},
                status=400
            )
        qty = int(item.get('qty', 1))
        item_total = product.price * qty
        server_total += item_total
        validated_items.append({
            'product': product,
            'qty': qty,
            'price': product.price,
            'subtotal': item_total,
        })

    # Use server-calculated total (don't trust client)
    total = server_total

    # Create Order rows in database
    created_orders = []
    for vi in validated_items:
        order = Order.objects.create(
            product=vi['product'],
            customer=request.user,
            quantity=vi['qty'],
            pickup_time=pickup_time,
            order_type=order_type,
            date=order_date,
            student_id=request.user.username,
            status=False,  # Pending
        )
        created_orders.append(order.order_id)

    order_ref = f"LCT-{created_orders[0]:04d}"

    # Create Razorpay order
    try:
        razorpay_order = create_razorpay_order(
            amount_rupees=total,
            receipt=order_ref,
            notes={
                'student': request.user.username,
                'order_ref': order_ref,
                'items_count': str(len(items)),
            }
        )
    except Exception as e:
        # Rollback: delete created orders
        Order.objects.filter(order_id__in=created_orders).delete()
        logger.error(f"Razorpay order creation failed: {e}")
        return JsonResponse(
            {'status': 'error', 'message': 'Payment gateway error. Please try again.'},
            status=500
        )

    # Create Payment record
    payment = Payment.objects.create(
        user=request.user,
        order_group=order_ref,
        amount=total,
        amount_paise=int(total * 100),
        razorpay_order_id=razorpay_order['id'],
        status='created',
    )

    return JsonResponse({
        'status': 'success',
        'order_id': razorpay_order['id'],
        'amount': razorpay_order['amount'],
        'currency': razorpay_order['currency'],
        'key_id': settings.RAZORPAY_KEY_ID,
        'order_ref': order_ref,
        'order_ids': created_orders,
        'payment_uuid': str(payment.payment_uuid),
    })


@login_required
@require_POST
def verify_payment(request):
    """
    Receives payment response from Razorpay Checkout and verifies the signature.

    POST JSON:
    {
        "razorpay_payment_id": "pay_xxxxx",
        "razorpay_order_id": "order_xxxxx",
        "razorpay_signature": "xxxxx",
        "order_ref": "LCT-0001"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_order_id = data.get('razorpay_order_id', '')
    razorpay_signature = data.get('razorpay_signature', '')
    order_ref = data.get('order_ref', '')

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        logger.error(f"Missing payment data: pid={razorpay_payment_id}, oid={razorpay_order_id}, sig={'yes' if razorpay_signature else 'no'}")
        return JsonResponse({'status': 'error', 'message': 'Missing payment data'}, status=400)

    # Find the payment record
    try:
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id, user=request.user)
        logger.info(f"Found payment record: {payment.payment_uuid}, status={payment.status}")
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for order_id={razorpay_order_id}, user={request.user}")
        return JsonResponse({'status': 'error', 'message': 'Payment not found'}, status=404)

    # Prevent duplicate processing
    if payment.is_verified and payment.status == 'captured':
        logger.info(f"Payment already verified: {payment.payment_uuid}")
        return JsonResponse({
            'status': 'success',
            'message': 'Payment already verified',
            'redirect_url': f'/payments/success/{order_ref}/',
        })

    # Verify signature
    logger.info(f"Verifying signature: order_id={razorpay_order_id}, payment_id={razorpay_payment_id}")
    is_valid = verify_payment_signature(
        razorpay_order_id, razorpay_payment_id, razorpay_signature
    )
    logger.info(f"Signature verification result: {is_valid}")

    if is_valid:
        # Process the successful payment
        process_successful_payment(payment, {
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })

        return JsonResponse({
            'status': 'success',
            'message': 'Payment verified successfully',
            'redirect_url': f'/payments/success/{order_ref}/',
        })
    else:
        # Mark as failed
        payment.status = 'failed'
        payment.is_verified = False
        payment.remarks = 'Signature verification failed'
        payment.save()
        logger.error(f"Signature verification FAILED for payment {razorpay_payment_id}")

        return JsonResponse({
            'status': 'error',
            'message': 'Payment verification failed',
            'redirect_url': f'/payments/failed/{order_ref}/',
        }, status=400)


@login_required
@require_POST
def record_failure_api(request):
    """
    AJAX endpoint: Records a client-side Razorpay payment failure
    along with the specific error message.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    razorpay_order_id = data.get('razorpay_order_id', '')
    error_description = data.get('error_description', 'Payment failed')

    if not razorpay_order_id:
        return JsonResponse({'status': 'error', 'message': 'Missing order ID'}, status=400)

    try:
        payment = Payment.objects.get(razorpay_order_id=razorpay_order_id, user=request.user)
        payment.status = 'failed'
        payment.remarks = error_description
        payment.save()
        logger.info(f"Recorded failure for order {razorpay_order_id}: {error_description}")
        return JsonResponse({'status': 'success'})
    except Payment.DoesNotExist:
        logger.warning(f"Payment not found for failure recording: order_id={razorpay_order_id}")
        return JsonResponse({'status': 'error', 'message': 'Payment not found'}, status=404)



@login_required
def payment_success(request, order_ref):
    """Renders the payment success page with order details and QR code."""
    try:
        payment = Payment.objects.get(order_group=order_ref, user=request.user)
    except Payment.DoesNotExist:
        return redirect('home')

    # Get order items for display
    order_ids = _get_order_ids(payment)
    orders = Order.objects.filter(order_id__in=order_ids).select_related('product')

    cart_items = []
    for order in orders:
        cart_items.append({
            'name': order.product.name,
            'qty': order.quantity,
            'price': order.product.price,
            'subtotal': order.product.price * order.quantity,
        })

    # Extract invoice and QR from remarks
    invoice_number = ''
    qr_url = ''
    if payment.remarks:
        parts = payment.remarks.split(' | ')
        for part in parts:
            if part.startswith('Invoice:'):
                invoice_number = part.replace('Invoice: ', '').strip()
            elif part.startswith('QR:'):
                qr_relative = part.replace('QR: ', '').strip()
                qr_url = f"{settings.MEDIA_URL}{qr_relative}"

    pickup_slot, _ = calculate_pickup_slot()

    context = {
        'payment': payment,
        'order_ref': order_ref,
        'cart_items': cart_items,
        'invoice_number': invoice_number,
        'qr_url': qr_url,
        'pickup_slot': pickup_slot,
        'total': payment.amount,
    }
    return render(request, 'payments/payment_success.html', context)


@login_required
def payment_failed(request, order_ref):
    """Renders the payment failed page with retry option."""
    try:
        payment = Payment.objects.get(order_group=order_ref, user=request.user)
    except Payment.DoesNotExist:
        return redirect('home')

    context = {
        'payment': payment,
        'order_ref': order_ref,
        'error_reason': payment.remarks or 'Payment could not be completed.',
    }
    return render(request, 'payments/payment_failed.html', context)


@login_required
def download_receipt(request, order_ref):
    """Generates and returns a PDF receipt for download."""
    try:
        payment = Payment.objects.get(order_group=order_ref, user=request.user)
    except Payment.DoesNotExist:
        return redirect('home')

    if payment.status != 'captured':
        return redirect('home')

    # Get order items
    order_ids = _get_order_ids(payment)
    orders = Order.objects.filter(order_id__in=order_ids).select_related('product')

    cart_items = []
    for order in orders:
        cart_items.append({
            'name': order.product.name,
            'qty': order.quantity,
            'price': str(order.product.price),
            'subtotal': str(order.product.price * order.quantity),
        })

    # Extract invoice number from remarks
    invoice_number = ''
    if payment.remarks and 'Invoice:' in payment.remarks:
        invoice_number = payment.remarks.split('Invoice: ')[1].split(' |')[0].strip()

    pickup_slot, _ = calculate_pickup_slot()

    pdf_buffer = generate_receipt_pdf(
        payment=payment,
        cart_items=cart_items,
        order_ref=order_ref,
        invoice_number=invoice_number or order_ref,
        pickup_slot=pickup_slot,
    )

    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{order_ref}.pdf"'
    return response


@login_required
def retry_payment(request, order_ref):
    """Creates a new Razorpay order for a previously failed payment."""
    try:
        payment = Payment.objects.get(order_group=order_ref, user=request.user)
    except Payment.DoesNotExist:
        return redirect('home')

    if payment.status == 'captured':
        return redirect('payment_success', order_ref=order_ref)

    # Create a new Razorpay order with the same amount
    try:
        razorpay_order = create_razorpay_order(
            amount_rupees=payment.amount,
            receipt=order_ref,
            notes={
                'student': request.user.username,
                'order_ref': order_ref,
                'retry': 'true',
            }
        )
    except Exception as e:
        logger.error(f"Retry Razorpay order creation failed: {e}")
        return JsonResponse(
            {'status': 'error', 'message': 'Payment gateway error.'},
            status=500
        )

    # Update payment with new Razorpay order
    payment.razorpay_order_id = razorpay_order['id']
    payment.status = 'created'
    payment.remarks = ''
    payment.save()

    return JsonResponse({
        'status': 'success',
        'order_id': razorpay_order['id'],
        'amount': razorpay_order['amount'],
        'currency': razorpay_order['currency'],
        'key_id': settings.RAZORPAY_KEY_ID,
        'order_ref': order_ref,
    })


def _get_order_ids(payment):
    """Gets order IDs associated with a payment's order group."""
    from .services import _get_order_ids_from_group
    return _get_order_ids_from_group(payment.order_group)
