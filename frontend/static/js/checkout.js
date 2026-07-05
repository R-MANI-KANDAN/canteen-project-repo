// Description: Razorpay Checkout integration — reads cart, creates order via AJAX, opens Checkout popup, verifies payment.

(function () {
  'use strict';

  /* ── Utilities ─────────────────────────────────────────────────────────── */
  function getCsrf() {
    const cookies = document.cookie.split(';');
    for (const c of cookies) {
      const [k, v] = c.trim().split('=');
      if (k === 'csrftoken') return decodeURIComponent(v);
    }
    return '';
  }

  function getCart() {
    return JSON.parse(localStorage.getItem('cartItems') || '[]');
  }

  function showToast(msg, type = 'info') {
    const toast = document.getElementById('checkoutToast');
    if (!toast) return;
    toast.textContent = msg;
    toast.className = `toast ${type} show`;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove('show'), 4000);
  }

  function setPayBtnLoading(loading) {
    const btn = document.getElementById('payNowBtn');
    if (!btn) return;
    btn.disabled = loading;
    if (loading) {
      btn.classList.add('loading');
    } else {
      btn.classList.remove('loading');
    }
  }

  /* ── Cart Rendering ────────────────────────────────────────────────────── */
  function renderCheckoutSummary() {
    const cart = getCart();
    const tbody = document.getElementById('checkoutItemsBody');
    const subtotalEl = document.getElementById('checkoutSubtotal');
    const totalEl = document.getElementById('checkoutTotal');
    const payLabelEl = document.getElementById('payAmountLabel');

    if (!tbody) return;

    if (!cart.length) {
      document.querySelector('.checkout-page').innerHTML = `
        <div class="checkout-empty">
          <div class="icon">🛒</div>
          <h3>Your cart is empty</h3>
          <p>Add items from the menu before checking out.</p>
          <a href="/" class="back-btn" style="margin-top:1.25rem;">← Back to Home</a>
        </div>`;
      return;
    }

    let subtotal = 0;
    tbody.innerHTML = cart.map(item => {
      const tot = parseFloat(item.price) * item.qty;
      subtotal += tot;
      return `
        <tr>
          <td>
            <div class="item-info">
              <img src="${item.img || ''}" alt="${item.name}"
                   onerror="this.style.display='none'">
              <span class="item-name">${item.name}</span>
            </div>
          </td>
          <td class="col-qty">${item.qty}</td>
          <td class="col-price">₹${parseFloat(item.price).toFixed(2)}</td>
          <td class="col-subtotal">₹${tot.toFixed(2)}</td>
        </tr>`;
    }).join('');

    if (subtotalEl) subtotalEl.textContent = `₹${subtotal.toFixed(2)}`;
    if (totalEl)    totalEl.textContent    = `₹${subtotal.toFixed(2)}`;
    if (payLabelEl) payLabelEl.textContent = `Pay ₹${subtotal.toFixed(2)}`;
  }

  /* ── Checkout Chips ────────────────────────────────────────────────────── */
  let selectedTime = '';
  let selectedType = 'Dine In';

  function initChips() {
    document.querySelectorAll('#timeChips .checkout-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('#timeChips .checkout-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        selectedTime = chip.dataset.value;
      });
    });

    document.querySelectorAll('#typeChips .checkout-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('#typeChips .checkout-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        selectedType = chip.dataset.value;
      });
    });

    // Set defaults from session storage (populated by cart page)
    const savedTime = sessionStorage.getItem('checkoutPickupTime');
    const savedType = sessionStorage.getItem('checkoutOrderType');
    if (savedTime) {
      const chip = document.querySelector(`#timeChips .checkout-chip[data-value="${savedTime}"]`);
      if (chip) {
        document.querySelectorAll('#timeChips .checkout-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        selectedTime = savedTime;
      }
    }
    if (savedType) {
      const chip = document.querySelector(`#typeChips .checkout-chip[data-value="${savedType}"]`);
      if (chip) {
        document.querySelectorAll('#typeChips .checkout-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        selectedType = savedType;
      }
    }

    // First active chip as fallback
    const activeTime = document.querySelector('#timeChips .checkout-chip.active');
    if (activeTime && !selectedTime) selectedTime = activeTime.dataset.value;
  }

  /* ── Razorpay Flow ─────────────────────────────────────────────────────── */
  function initiatePayment() {
    const cart = getCart();
    if (!cart.length) {
      showToast('Your cart is empty.', 'error');
      return;
    }

    const dateEl = document.getElementById('checkoutDate');
    const date = dateEl ? dateEl.value : new Date().toISOString().split('T')[0];

    setPayBtnLoading(true);

    const payload = {
      items: cart.map(i => ({
        id: i.id,
        name: i.name,
        qty: i.qty,
        price: i.price,
      })),
      pickup_time: selectedTime,
      order_type: selectedType,
      date: date,
      total: cart.reduce((s, i) => s + parseFloat(i.price) * i.qty, 0),
    };

    console.log('[Checkout] Creating order with payload:', payload);

    // Step 1: Create Razorpay order on backend
    fetch('/payments/create-order/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
      },
      body: JSON.stringify(payload),
    })
      .then(r => {
        console.log('[Checkout] Create-order response status:', r.status);
        return r.json();
      })
      .then(data => {
        console.log('[Checkout] Create-order response data:', data);
        if (data.status !== 'success') {
          showToast(data.message || 'Failed to create order. Please try again.', 'error');
          setPayBtnLoading(false);
          return;
        }
        openRazorpayCheckout(data);
      })
      .catch(err => {
        console.error('[Checkout] Create-order fetch error:', err);
        showToast('Network error. Please check your connection and try again.', 'error');
        setPayBtnLoading(false);
      });
  }

  function openRazorpayCheckout(orderData) {
    console.log('[Checkout] Opening Razorpay popup with:', {
      key: orderData.key_id,
      amount: orderData.amount,
      order_id: orderData.order_id,
      order_ref: orderData.order_ref,
    });

    // Build prefill dynamically to avoid passing empty or invalid strings (which causes 400 Bad Request)
    const prefill = {};
    if (window.CHECKOUT_USER_NAME && window.CHECKOUT_USER_NAME.trim() !== '') {
      prefill.name = window.CHECKOUT_USER_NAME.trim();
    }
    if (window.CHECKOUT_USER_EMAIL && window.CHECKOUT_USER_EMAIL.trim() !== '' && window.CHECKOUT_USER_EMAIL.includes('@')) {
      prefill.email = window.CHECKOUT_USER_EMAIL.trim();
    }

    // Razorpay options
    const options = {
      key: orderData.key_id,
      amount: orderData.amount,           // in paise
      currency: orderData.currency || 'INR',
      name: 'LICET Cafeteria',
      description: `Order ${orderData.order_ref}`,
      order_id: orderData.order_id,       // Razorpay order_id
      prefill: prefill,
      theme: {
        color: '#f97316',
      },
      modal: {
        ondismiss: function () {
          console.log('[Checkout] Razorpay popup dismissed by user');
          showToast('Payment cancelled. You can retry any time.', 'info');
          setPayBtnLoading(false);
        },
        escape: true,
        backdropclose: false,
      },
      handler: function (response) {
        // Step 2: Verify payment signature on backend
        console.log('[Checkout] Payment handler called — SUCCESS from Razorpay:', response);
        verifyPayment(response, orderData.order_ref, orderData.payment_uuid);
      },
    };

    const rzp = new window.Razorpay(options);

    rzp.on('payment.failed', function (response) {
      console.error('[Checkout] payment.failed event:', JSON.stringify(response.error, null, 2));
      setPayBtnLoading(false);
      const errMsg = response.error?.description || 'Payment failed.';
      showToast(errMsg, 'error');

      // Record failure to server
      fetch('/payments/record-failure/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify({
          razorpay_order_id: orderData.order_id,
          error_description: errMsg,
        }),
      })
        .finally(() => {
          setTimeout(() => {
            window.location.href = `/payments/failed/${orderData.order_ref}/`;
          }, 1500);
        });
    });

    rzp.open();
  }

  function verifyPayment(response, orderRef, paymentUuid) {
    console.log('[Checkout] Verifying payment:', {
      razorpay_payment_id: response.razorpay_payment_id,
      razorpay_order_id: response.razorpay_order_id,
      razorpay_signature: response.razorpay_signature?.substring(0, 20) + '...',
      order_ref: orderRef,
    });

    fetch('/payments/verify/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
      },
      body: JSON.stringify({
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_order_id: response.razorpay_order_id,
        razorpay_signature: response.razorpay_signature,
        order_ref: orderRef,
        payment_uuid: paymentUuid,
      }),
    })
      .then(r => {
        console.log('[Checkout] Verify response status:', r.status);
        return r.json();
      })
      .then(data => {
        console.log('[Checkout] Verify response data:', data);
        if (data.status === 'success') {
          // Clear cart only after server confirms
          localStorage.setItem('cartItems', '[]');
          sessionStorage.removeItem('checkoutPickupTime');
          sessionStorage.removeItem('checkoutOrderType');
          // Update nav badge
          const badge = document.getElementById('nav-cart-badge');
          if (badge) badge.textContent = '0';
          window.location.href = data.redirect_url || `/payments/success/${orderRef}/`;
        } else {
          console.error('[Checkout] Verification failed:', data);
          showToast(data.message || 'Verification failed. Contact support.', 'error');
          setPayBtnLoading(false);
          setTimeout(() => {
            window.location.href = `/payments/failed/${orderRef}/`;
          }, 2500);
        }
      })
      .catch(err => {
        console.error('[Checkout] Verify fetch error:', err);
        showToast('Verification network error. Please contact support.', 'error');
        setPayBtnLoading(false);
      });
  }

  /* ── Retry Payment (on failed page) ───────────────────────────────────── */
  window.retryPayment = function (orderRef) {
    const btn = document.getElementById('retryBtn');
    if (btn) {
      btn.disabled = true;
      btn.classList.add('loading');
    }

    fetch(`/payments/retry/${orderRef}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrf() },
    })
      .then(r => r.json())
      .then(data => {
        if (data.status !== 'success') {
          alert(data.message || 'Could not retry payment.');
          if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
          return;
        }

        // Build prefill dynamically to avoid passing empty or invalid strings (which causes 400 Bad Request)
        const prefill = {};
        if (window.CHECKOUT_USER_NAME && window.CHECKOUT_USER_NAME.trim() !== '') {
          prefill.name = window.CHECKOUT_USER_NAME.trim();
        }
        if (window.CHECKOUT_USER_EMAIL && window.CHECKOUT_USER_EMAIL.trim() !== '' && window.CHECKOUT_USER_EMAIL.includes('@')) {
          prefill.email = window.CHECKOUT_USER_EMAIL.trim();
        }

        const options = {
          key: data.key_id,
          amount: data.amount,
          currency: data.currency || 'INR',
          name: 'LICET Cafeteria',
          description: `Retry - Order ${data.order_ref}`, // Changed em-dash to standard ASCII hyphen
          order_id: data.order_id,
          prefill: prefill,
          theme: { color: '#f97316' },
          modal: {
            ondismiss: function () {
              if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
            },
          },
          handler: function (response) {
            verifyPayment(response, data.order_ref, null);
          },
        };
        const rzp = new window.Razorpay(options);
        rzp.on('payment.failed', function (response) {
          console.error('[Checkout] retry payment.failed event:', JSON.stringify(response.error, null, 2));
          if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
          const errMsg = response.error?.description || 'Payment failed.';
          
          fetch('/payments/record-failure/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify({
              razorpay_order_id: data.order_id,
              error_description: errMsg,
            }),
          }).finally(() => {
            setTimeout(() => {
              window.location.href = `/payments/failed/${data.order_ref}/`;
            }, 1500);
          });
        });
        rzp.open();
      })
      .catch(() => {
        alert('Network error. Please try again.');
        if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
      });
  };

  /* ── Init ──────────────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    // Set today's date on checkout date picker
    const dateEl = document.getElementById('checkoutDate');
    if (dateEl && !dateEl.value) {
      dateEl.value = new Date().toISOString().split('T')[0];
    }

    renderCheckoutSummary();
    initChips();

    // Attach pay button
    const payBtn = document.getElementById('payNowBtn');
    if (payBtn) {
      payBtn.addEventListener('click', initiatePayment);
    }
  });
})();
