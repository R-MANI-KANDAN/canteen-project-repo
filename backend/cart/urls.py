# Description: URL routing configurations for shopping cart operations.
from django.urls import path
from .views import cart_summary,cart_update,cart_delete,cart_add

urlpatterns = [
    path('cart_summary/', cart_summary , name='cart_summary'),
    path('add/',cart_add, name='cart_add'),
    path('delete/', cart_delete , name='cart_delete'),
    path('update/', cart_update , name='cart_update'),
 
 ]
    
