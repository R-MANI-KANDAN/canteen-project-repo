# Razorpay Webhooks Integration Guide

This guide details the architecture, configuration, and implementation of Razorpay webhooks and APIs within the **LICET Cafeteria** canteen project.

---

## 1. Webhooks vs. APIs

| Aspect | APIs | Webhooks (Web Callback / Reverse API) |
| :--- | :--- | :--- |
| **Data Flow** | Pull-based (Django requests status updates) | Push-based (Razorpay pushes event notifications) |
| **Timing** | On-demand (typically initiated via client actions) | Real-time (sent automatically when events occur) |
| **Resource Efficiency** | Requires polling or periodic API calls | Event-driven, low resource footprint |

### Standard Checkout Flow Recommendation
* **Immediate Client confirmation**: The frontend payment checkout widget uses the checkout handler function to verify payment signatures immediately upon customer action and redirect them to a success/failure page.
* **Server-to-Server Webhook verification**: Webhooks serve as the source of truth for payment status automation (such as completing orders, late authorizations, or refund tracking), ensuring notifications are received even if the user closes their browser or has network failure.

---

## 2. Current Implementation Architecture

In the `payments` application, we have integrated Razorpay checkout and webhooks to manage payments securely.

### Directory Structure
```text
payments/
├── models.py      # Database models for payments and webhook logging
├── services.py    # Core Razorpay client services & signature verifiers
├── urls.py        # Webhook routing endpoints
├── views.py       # Checkout views and callback verifications
└── webhooks.py    # Incoming webhook event handlers
```

---

## 3. How Webhooks are Handled in Code

### Endpoint Configuration
The webhook endpoint is defined in `urls.py` and maps `/payments/webhook/` to the `webhook_handler` view inside `webhooks.py`:

```python
# payments/webhooks.py
@csrf_exempt
@require_POST
def webhook_handler(request):
    ...
```

### Signature Verification
Webhooks are verified securely in `services.py` using the Razorpay SDK Utility `verify_webhook_signature`. This verifies that the request payload was indeed signed by Razorpay using our configured `RAZORPAY_WEBHOOK_SECRET`:

```python
# payments/services.py
def verify_webhook_signature(request_body, signature):
    client = get_razorpay_client()
    try:
        client.utility.verify_webhook_signature(
            request_body,
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
```

### Idempotency & Logging
To prevent processing the same webhook multiple times (which Razorpay may resend if a 200 OK is not returned quickly), the handler uses the `WebhookLog` model in `models.py`:

1. It extracts `X-Razorpay-Event-Id` and logs it to `WebhookLog`.
2. If `WebhookLog.objects.filter(event_id=event_id, is_processed=True)` already exists, the view returns a `200 OK` response immediately, skipping duplicate processing:

```python
# payments/webhooks.py
existing_log = WebhookLog.objects.filter(event_id=event_id).first()
if existing_log and existing_log.is_processed:
    return JsonResponse({'status': 'ok', 'message': 'Already processed'})
```

---

## 4. Webhook Event Handlers
The current implementation handles several webhook events:

1. **`payment.authorized`**: Handles late authorizations (e.g., if a user closed their browser page mid-transaction). The server changes the payment status to `authorized` and initiates capturing choices based on business requirements.
2. **`payment.captured`**: The core webhook event. It updates the payment status to `captured`, retrieves payment details from the Razorpay API, generates an invoice number, and creates a QR confirmation code.
3. **`payment.failed`**: Logs the failure reason in `remarks` and marks status as `failed` to allow retry options.
4. **`order.paid`**: Double-verifies that the parent order is fully paid.
5. **`refund.created` / `refund.processed`**: Marks payment as refunded and logs details.

---

## 5. Setup & Environment Variables

Make sure the following variables are specified in your `.env` configuration file:

```env
RAZORPAY_KEY_ID=rzp_test_xxxxxx
RAZORPAY_KEY_SECRET=xxxxxx
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here
```

### In Razorpay Dashboard Settings:
1. Go to **Settings > Webhooks** in your Razorpay Dashboard.
2. Configure the webhook URL pointing to your deployed Django domain:
   `https://<your-domain>/payments/webhook/`
3. Enter the Webhook Secret key matching your `.env`'s `RAZORPAY_WEBHOOK_SECRET`.
4. Subscribe to the following active events:
   - `payment.authorized`
   - `payment.captured`
   - `payment.failed`
   - `order.paid`
   - `refund.processed`
