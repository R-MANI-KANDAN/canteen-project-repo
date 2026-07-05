# Description: Database models for payment tracking and webhook audit logging.
import uuid
from django.db import models
from django.contrib.auth.models import User
from base.models import Order


class Payment(models.Model):
    """
    Tracks individual Razorpay payment transactions.
    Each payment is linked to one or more Order rows (grouped by order_group).
    """

    STATUS_CHOICES = [
        ('created', 'Created'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('netbanking', 'Net Banking'),
        ('wallet', 'Wallet'),
        ('emi', 'EMI'),
        ('other', 'Other'),
    ]

    payment_uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='payments'
    )
    # Links to the first order in a group (order_group ties the rest)
    order_group = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text='Order reference like LCT-0001 that groups multiple Order rows'
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Amount in rupees'
    )
    amount_paise = models.PositiveIntegerField(
        default=0, help_text='Amount in paise sent to Razorpay'
    )
    currency = models.CharField(max_length=3, default='INR')

    # Razorpay references
    razorpay_order_id = models.CharField(
        max_length=100, blank=True, db_index=True
    )
    razorpay_payment_id = models.CharField(
        max_length=100, blank=True, db_index=True
    )
    razorpay_signature = models.CharField(max_length=500, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='created'
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default='other'
    )
    is_verified = models.BooleanField(
        default=False, help_text='Signature verification passed'
    )
    webhook_received = models.BooleanField(
        default=False, help_text='Webhook confirmation received'
    )
    webhook_event = models.CharField(
        max_length=50, blank=True,
        help_text='Last webhook event type received'
    )

    # Metadata
    remarks = models.TextField(blank=True, help_text='Error messages or notes')
    transaction_time = models.DateTimeField(
        null=True, blank=True, help_text='When payment was completed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f"Payment {self.razorpay_payment_id or self.payment_uuid} — ₹{self.amount} ({self.status})"


class WebhookLog(models.Model):
    """
    Audit trail for all incoming Razorpay webhook events.
    Used for idempotency checks and debugging.
    """

    event_id = models.CharField(
        max_length=100, unique=True,
        help_text='Razorpay event ID for idempotency'
    )
    event_type = models.CharField(
        max_length=50, help_text='e.g. payment.captured'
    )
    razorpay_order_id = models.CharField(
        max_length=100, blank=True, db_index=True
    )
    razorpay_payment_id = models.CharField(
        max_length=100, blank=True, db_index=True
    )
    payload = models.JSONField(
        help_text='Full webhook payload'
    )
    is_verified = models.BooleanField(
        default=False, help_text='Signature verified'
    )
    is_processed = models.BooleanField(
        default=False, help_text='Successfully processed'
    )
    error_message = models.TextField(
        blank=True, help_text='Processing errors'
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Webhook Log'
        verbose_name_plural = 'Webhook Logs'

    def __str__(self):
        return f"[{self.event_type}] {self.event_id} — {'✓' if self.is_processed else '✗'}"
