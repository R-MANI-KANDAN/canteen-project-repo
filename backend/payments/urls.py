# Description: URL routing for the payments app.
from django.urls import path
from . import views
from . import webhooks

urlpatterns = [
    # Checkout page
    path('checkout/', views.checkout_view, name='payment_checkout'),

    # AJAX: Create Razorpay order
    path('create-order/', views.create_order_api, name='create_order'),

    # AJAX: Verify payment signature
    path('verify/', views.verify_payment, name='verify_payment'),

    # AJAX: Record client-side failure
    path('record-failure/', views.record_failure_api, name='record_failure'),

    # Result pages
    path('success/<str:order_ref>/', views.payment_success, name='payment_success'),
    path('failed/<str:order_ref>/', views.payment_failed, name='payment_failed'),

    # Receipt download
    path('receipt/<str:order_ref>/', views.download_receipt, name='download_receipt'),

    # Retry failed payment
    path('retry/<str:order_ref>/', views.retry_payment, name='retry_payment'),

    # Razorpay webhook (CSRF-exempt)
    path('webhook/', webhooks.webhook_handler, name='razorpay_webhook'),
]
