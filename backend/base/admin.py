# Description: Admin interface configurations to manage base application database models.
from django.contrib import admin
from . import models


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_id', 'product', 'customer', 'quantity',
        'payment_status', 'pickup_slot', 'order_type', 'date', 'status',
    )
    list_filter = ('payment_status', 'order_type', 'status', 'date')
    search_fields = (
        'student_id', 'invoice_number',
        'customer__username', 'customer__email',
        'product__name',
    )
    readonly_fields = ('order_id', 'qr_token', 'invoice_number')
    date_hierarchy = 'date'
    ordering = ('-order_id',)

    fieldsets = (
        ('Order Info', {
            'fields': ('order_id', 'product', 'customer', 'quantity', 'student_id', 'date')
        }),
        ('Delivery', {
            'fields': ('order_type', 'pickup_time', 'pickup_slot', 'status')
        }),
        ('Payment', {
            'fields': ('payment_status', 'grand_total', 'invoice_number', 'qr_token'),
        }),
    )


admin.site.register(models.Customer)
admin.site.register(models.Product)
admin.site.register(models.Category)
admin.site.register(models.Landing_img)
