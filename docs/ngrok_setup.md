# ngrok Setup for Local Webhook Testing

Razorpay cannot reach `localhost` for webhook delivery. **ngrok** creates a secure public HTTPS tunnel to your local Django server.

---

## Step 1 — Install ngrok

### Windows (recommended via Chocolatey)
```powershell
choco install ngrok
```

### Or download manually
Go to [https://ngrok.com/download](https://ngrok.com/download), download the Windows zip, and extract `ngrok.exe` to a folder in your `PATH`.

---

## Step 2 — Create a Free Account & Authenticate

1. Sign up at [https://dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup)
2. Copy your **Authtoken** from [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
3. Run once to configure:
```powershell
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

---

## Step 3 — Start Your Django Server

In one terminal:
```powershell
cd "C:\7th sem activities\canteen project\LICET-Cafeteria"
.\venv\Scripts\python.exe manage.py runserver 8000
```

---

## Step 4 — Start ngrok Tunnel

In a **second** terminal:
```powershell
ngrok http 8000
```

You'll see output like:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8000
```

Copy the **HTTPS** URL (e.g., `https://abc123.ngrok-free.app`).

> ⚠️ The free ngrok URL changes every time you restart ngrok. You'll need to update Razorpay Dashboard each session.

---

## Step 5 — Configure Razorpay Webhook

1. Go to [https://dashboard.razorpay.com/app/webhooks](https://dashboard.razorpay.com/app/webhooks)
2. Click **+ Add New Webhook**
3. Fill in:
   - **Webhook URL**: `https://abc123.ngrok-free.app/payments/webhook/`
   - **Secret**: Generate a strong random string (e.g., `openssl rand -hex 32`)
4. Subscribe to these **Active Events**:
   - ✅ `payment.authorized`
   - ✅ `payment.captured`
   - ✅ `payment.failed`
   - ✅ `order.paid`
   - ✅ `refund.processed`
5. Click **Save**

---

## Step 6 — Update `.env`

Open `backend/.env` and set the webhook secret you just created:
```env
RAZORPAY_WEBHOOK_SECRET=the_secret_you_generated_above
```

Then restart your Django server:
```powershell
.\venv\Scripts\python.exe manage.py runserver 8000
```

---

## Step 7 — Test a Webhook

1. In the Razorpay Dashboard, go to your webhook → **Test Payload**
2. Select event type `payment.captured` and click **Send Test Payload**
3. Check your Django server terminal — you should see:
   ```
   [INFO] payments.webhooks: Webhook signature invalid for event ...
   ```
   (This is expected for test payloads since the signature won't match. For real payments it will work.)

4. Check the ngrok web interface at [http://localhost:4040](http://localhost:4040) to inspect all requests and responses.

---

## Step 8 — End-to-End Test

Use these Razorpay test credentials in the Checkout popup:

| Method | Test Value |
|:-------|:-----------|
| **Card** | `4111 1111 1111 1111`, any future expiry, any CVV |
| **UPI (success)** | `success@razorpay` |
| **UPI (failure)** | `failure@razorpay` |
| **Net Banking** | Select any bank, complete the dummy flow |

After a successful test payment, verify:
- ✅ `Payment` record in Django admin → status = `captured`, `is_verified = True`
- ✅ `WebhookLog` record in admin → `is_processed = True`
- ✅ QR code image in `backend/media/qr_codes/`
- ✅ Success page shows order details and QR code

---

## Troubleshooting

| Issue | Fix |
|:------|:----|
| Webhook shows 400 | Check `RAZORPAY_WEBHOOK_SECRET` matches Dashboard |
| ngrok URL expired | Restart ngrok, update Dashboard URL |
| `ALLOWED_HOSTS` error | Add ngrok domain to `ALLOWED_HOSTS` in `settings.py` |
| Signature mismatch | Ensure raw body is read before JSON parse (already handled) |

### Add ngrok domain to ALLOWED_HOSTS (during dev only)
```python
# settings.py — temporarily during webhook testing
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.ngrok-free.app', 'testserver']
```
