# Description: URL routing configuration for base views (home, login, registration, menus).
from django.urls import path
from . import views

urlpatterns = [
    # Home / Auth
    path('',                  views.home,                name='home'),
    path('home/',             views.home,                name='home'),
    path('login/',            views.custom_login,        name='login'),
    path('logout/',           views.custom_logout,       name='logout'),
    path('signup/',           views.authView,            name='auth'),

    # Profile
    path('update-profile/',       views.update_profile,       name='update_profile'),
    path('update-profile-ajax/',  views.update_profile_ajax,  name='update_profile_ajax'),

    # Menu categories
    path('ready-to-grab/',    views.ready_to_grab,   name='ready_to_grab'),
    path('cooked-to-serve/',  views.cooked_to_serve, name='cooked_to_serve'),
    path('beverages/',        views.beverages,        name='beverages'),
    path('snacks/',           views.snacks,           name='snacks'),
    path('sidedish/',         views.sidedish,         name='sidedish'),

    # Contact
    path('contact/',          views.contact,          name='contact'),

    # Checkout
    path('checkout/',         views.checkout_order,   name='checkout_order'),

    # Kitchen (staff only)
    path('kitchen/',                        views.kitchen_dashboard,   name='kitchen_dashboard'),
    path('kitchen/toggle/<int:order_id>/',  views.toggle_order_status, name='toggle_order_status'),
]
