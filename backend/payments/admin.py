# Description: Admin registration for Payment and WebhookLog models.
from django.contrib import admin
from .models import Payment, WebhookLog


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'order_group', 'user', 'amount', 'status', 'payment_method',
        'is_verified', 'webhook_received', 'razorpay_payment_id', 'created_at',
    )
    list_filter = ('status', 'payment_method', 'is_verified', 'webhook_received')
    search_fields = (
        'order_group', 'razorpay_order_id', 'razorpay_payment_id',
        'user__username', 'user__email',
    )
    readonly_fields = (
        'payment_uuid', 'razorpay_order_id', 'razorpay_payment_id',
        'razorpay_signature', 'is_verified', 'webhook_received',
        'webhook_event', 'transaction_time', 'created_at', 'updated_at',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Order Information', {
            'fields': ('payment_uuid', 'user', 'order_group', 'amount', 'amount_paise', 'currency')
        }),
        ('Razorpay Details', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')
        }),
        ('Status', {
            'fields': ('status', 'payment_method', 'is_verified', 'webhook_received', 'webhook_event')
        }),
        ('Metadata', {
            'fields': ('remarks', 'transaction_time', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = (
        'event_type', 'event_id', 'razorpay_order_id',
        'is_verified', 'is_processed', 'received_at',
    )
    list_filter = ('event_type', 'is_verified', 'is_processed')
    search_fields = ('event_id', 'razorpay_order_id', 'razorpay_payment_id')
    readonly_fields = (
        'event_id', 'event_type', 'razorpay_order_id', 'razorpay_payment_id',
        'payload', 'is_verified', 'received_at',
    )
    date_hierarchy = 'received_at'
    ordering = ('-received_at',)
