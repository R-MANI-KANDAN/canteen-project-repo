import json
import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .forms import CustomUserCreationForm, ProfileUpdateForm
from .models import Profile, Product, Order


# ─── Authentication ────────────────────────────────────────────────────────────

def authView(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        email    = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if User.objects.filter(username=email).exists():
            messages.error(request, 'A user with this email already exists.')
            return render(request, 'registration/signup.html', {'form': form})

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'registration/signup.html', {'form': form})

        if form.is_valid():
            user = User.objects.create_user(username=email, email=email, password=password1)
            Profile.objects.get_or_create(user=user)
            messages.success(request, 'Account created! Please log in.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/signup.html', {'form': form})


def custom_login(request):
    if request.method == 'POST':
        email    = request.POST.get('email', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        messages.error(request, 'Invalid email or password.')
        return redirect('login')
    return render(request, 'registration/login.html')


def custom_logout(request):
    logout(request)
    return redirect('login')


# ─── Home & Profile ────────────────────────────────────────────────────────────

@login_required
def home(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, 'registration/home.html', {'profile': profile})


@login_required
def update_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('home')
    else:
        form = ProfileUpdateForm(instance=profile)
    return render(request, 'registration/update_profile.html', {'form': form})


@login_required
@require_POST
def update_profile_ajax(request):
    """AJAX endpoint – saves student profile details to the database."""
    profile, _ = Profile.objects.get_or_create(user=request.user)

    # Text fields
    profile.year_of_study = request.POST.get('yearOfStudy', profile.year_of_study)
    profile.batch         = request.POST.get('batch', profile.batch)
    profile.department    = request.POST.get('department', profile.department)

    dob = request.POST.get('dateOfBirth', '')
    if dob:
        try:
            profile.date_of_birth = datetime.date.fromisoformat(dob)
        except ValueError:
            pass

    # Full name → split into first_name / last_name on the User model
    full_name = request.POST.get('fullName', '').strip()
    if full_name:
        parts = full_name.split(' ', 1)
        request.user.first_name = parts[0]
        request.user.last_name  = parts[1] if len(parts) > 1 else ''
        request.user.save()

    # Profile picture
    if 'profilePic' in request.FILES:
        profile.profile_picture = request.FILES['profilePic']

    profile.save()

    return JsonResponse({
        'status': 'success',
        'fullName': f"{request.user.first_name} {request.user.last_name}".strip(),
        'profilePicUrl': profile.profile_picture.url if profile.profile_picture else '',
    })


# ─── Menu Pages ───────────────────────────────────────────────────────────────

@login_required
def ready_to_grab(request):
    products = (Product.objects
                .filter(category__name__iexact='ready to grab', is_sale=True)
                .select_related('category')
                .order_by('sub_category', 'name'))
    return render(request, 'registration/ready_to_grab.html', {'products': products})


@login_required
def cooked_to_serve(request):
    products = (Product.objects
                .filter(category__name__iexact='cook to serve', is_sale=True)
                .select_related('category')
                .order_by('sub_category', 'name'))
    return render(request, 'registration/cooked_to_serve.html', {'products': products})


@login_required
def beverages(request):
    products = (Product.objects
                .filter(category__name__iexact='beverages', is_sale=True)
                .select_related('category')
                .order_by('sub_category', 'name'))
    return render(request, 'registration/beverages.html', {'products': products})


@login_required
def snacks(request):
    products = (Product.objects
                .filter(category__name__iexact='snacks', is_sale=True)
                .select_related('category')
                .order_by('sub_category', 'name'))
    return render(request, 'registration/snacks.html', {'products': products})


@login_required
def sidedish(request):
    products = (Product.objects
                .filter(category__name__iexact='side dishes', is_sale=True)
                .select_related('category')
                .order_by('sub_category', 'name'))
    return render(request, 'registration/sidedish.html', {'products': products})


def contact(request):
    return render(request, 'registration/contact.html')


# ─── Checkout ─────────────────────────────────────────────────────────────────

@login_required
@require_POST
def checkout_order(request):
    """
    Accepts JSON cart payload from the frontend, creates Order rows in the DB,
    and returns a real order reference number.

    Expected JSON body:
    {
        "items":      [{"id": 1, "qty": 2}, ...],
        "pickup_time": "12:45",
        "order_type":  "Dine In",
        "date":        "2025-06-22"
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    items       = data.get('items', [])
    pickup_time = data.get('pickup_time', '')
    order_type  = data.get('order_type', 'Dine In')
    date_str    = data.get('date', '')

    if not items:
        return JsonResponse({'status': 'error', 'message': 'Cart is empty'}, status=400)

    try:
        order_date = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        order_date = datetime.date.today()

    created_orders = []
    for item in items:
        product = get_object_or_404(Product, pk=item.get('id'))
        order = Order.objects.create(
            product     = product,
            customer    = request.user,
            quantity    = int(item.get('qty', 1)),
            pickup_time = pickup_time,
            order_type  = order_type,
            date        = order_date,
            student_id  = request.user.username,
        )
        created_orders.append(order.order_id)

    # Return the first order_id as the receipt reference
    return JsonResponse({
        'status':   'success',
        'order_ids': created_orders,
        'order_ref': f"LCT-{created_orders[0]:04d}",
    })


# ─── Kitchen Dashboard ────────────────────────────────────────────────────────

@login_required
def kitchen_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied. Staff only.')
        return redirect('home')

    pending   = (Order.objects.filter(status=False)
                 .select_related('product', 'customer')
                 .order_by('date', 'pickup_time'))
    completed = (Order.objects.filter(status=True)
                 .select_related('product', 'customer')
                 .order_by('-date', '-pickup_time')[:20])

    return render(request, 'registration/kitchen_dashboard.html', {
        'pending':   pending,
        'completed': completed,
    })


@login_required
@require_POST
def toggle_order_status(request, order_id):
    """Kitchen staff can mark orders as done."""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    order = get_object_or_404(Order, pk=order_id)
    order.status = not order.status
    order.save()
    return JsonResponse({'status': 'success', 'done': order.status})