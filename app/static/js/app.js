// SmartMess Resident Interactive Scripts (IST Localized)

// Toast notification helper
function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✅' : '⚠️'}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.2s ease';
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

// 1-Click Meal Response Handler (2-3 seconds response time)
async function submitMealResponse(mealId, responseType, buttonElement) {
  const card = document.getElementById(`meal-card-${mealId}`);
  const eatBtn = document.getElementById(`btn-eat-${mealId}`);
  const notEatBtn = document.getElementById(`btn-not-eat-${mealId}`);
  const statusBadge = document.getElementById(`status-badge-${mealId}`);

  // Prevent multiple rapid clicks
  if (eatBtn) eatBtn.disabled = true;
  if (notEatBtn) notEatBtn.disabled = true;

  try {
    const res = await fetch(`/api/meals/${mealId}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response: responseType })
    });

    const data = await res.json();

    if (!res.ok) {
      showToast(data.detail || 'Could not record response.', 'error');
      return;
    }

    // Update UI immediately
    if (responseType === 'will_eat') {
      if (eatBtn) {
        eatBtn.classList.add('selected');
        eatBtn.innerHTML = '✅ You are Eating';
      }
      if (notEatBtn) {
        notEatBtn.classList.remove('selected');
        notEatBtn.innerHTML = '❌ I will NOT eat';
      }
      if (card) {
        card.classList.remove('status-not-eating', 'status-unresponded');
        card.classList.add('status-will-eat');
      }
      if (statusBadge) {
        statusBadge.className = 'status-badge badge-will-eat';
        statusBadge.innerHTML = '🟢 Will Eat';
      }
      showToast(`Recorded: You WILL eat this meal! (Recorded at ${data.timestamp_ist || 'now'}) 🍽️`, 'success');
    } else {
      if (notEatBtn) {
        notEatBtn.classList.add('selected');
        notEatBtn.innerHTML = '❌ Recorded: NOT Eating';
      }
      if (eatBtn) {
        eatBtn.classList.remove('selected');
        eatBtn.innerHTML = '✅ I will eat';
      }
      if (card) {
        card.classList.remove('status-will-eat', 'status-unresponded');
        card.classList.add('status-not-eating');
      }
      if (statusBadge) {
        statusBadge.className = 'status-badge badge-not-eating';
        statusBadge.innerHTML = '🔴 Not Eating';
      }
      showToast(`Recorded: You will NOT eat. Thank you for saving food! 🌱 (${data.timestamp_ist || 'now'})`, 'success');
    }

  } catch (err) {
    console.error(err);
    showToast('Network error while saving response.', 'error');
  } finally {
    if (eatBtn) eatBtn.disabled = false;
    if (notEatBtn) notEatBtn.disabled = false;
  }
}

// Mark single notification as read
async function markNotificationAsRead(id, btnElement) {
  try {
    const res = await fetch(`/api/notifications/${id}/read`, { method: 'POST' });
    if (res.ok) {
      const item = document.getElementById(`notification-item-${id}`);
      if (item) {
        item.style.opacity = '0.6';
        item.classList.remove('unread');
      }
      if (btnElement) btnElement.remove();
      showToast('Marked as read', 'success');
    }
  } catch (e) {
    console.error(e);
  }
}

// Mark all notifications as read
async function markAllNotificationsRead() {
  try {
    const res = await fetch('/api/notifications/read-all', { method: 'POST' });
    if (res.ok) {
      document.querySelectorAll('.notification-item').forEach(el => {
        el.style.opacity = '0.6';
        el.classList.remove('unread');
      });
      const badge = document.getElementById('unread-notif-pill');
      if (badge) badge.style.display = 'none';
      showToast('All notifications marked as read', 'success');
    }
  } catch (e) {
    console.error(e);
  }
}

// Modal open/close helpers
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = 'auto';
  }
}

// Precise Countdown Timer with IST parsing
function updateDeadlineCountdowns() {
  const elements = document.querySelectorAll('[data-deadline]');
  const now = new Date();

  elements.forEach(el => {
    let deadlineStr = el.getAttribute('data-deadline');
    if (!deadlineStr) return;

    // Normalizing to ISO with IST (+05:30) offset if needed
    let isoStr = deadlineStr.trim();
    if (isoStr.indexOf('T') === -1) {
      isoStr = isoStr.replace(' ', 'T');
    }
    if (isoStr.indexOf('+') === -1 && isoStr.indexOf('Z') === -1) {
      isoStr = isoStr + '+05:30';
    }

    const deadline = new Date(isoStr);
    const diff = deadline.getTime() - now.getTime();

    if (diff <= 0) {
      el.innerHTML = '🔒 Deadline Passed';
      el.classList.add('badge-closed');
      el.classList.remove('badge-open');
    } else {
      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      if (hours > 0) {
        el.innerHTML = `⏱️ Closes in ${hours}h ${minutes}m ${seconds}s`;
      } else {
        el.innerHTML = `⏱️ Closes in ${minutes}m ${seconds}s`;
      }
    }
  });
}

// Student Real-Time Synchronization for Admin Pause / Close / Reopen Actions
let lastKnownMealStatuses = {};

async function syncStudentMealStatuses() {
  // Only run if student dashboard cards are present
  const cards = document.querySelectorAll('.meal-card');
  if (cards.length === 0) return;

  try {
    const res = await fetch('/api/realtime/student-sync');
    if (!res.ok) return;

    const data = await res.json();
    data.meals.forEach(m => {
      const card = document.getElementById(`meal-card-${m.id}`);
      if (!card) return;

      const countdownWrapper = document.getElementById(`countdown-wrapper-${m.id}`);
      const lockedBanner = document.getElementById(`locked-banner-${m.id}`);
      const responseContainer = document.getElementById(`response-container-${m.id}`);
      const prevStatus = lastKnownMealStatuses[m.id];

      // Detect if status changed dynamically
      if (prevStatus && prevStatus !== m.status) {
        if (m.status === 'paused') {
          showToast(`⏸️ Mess Admin has PAUSED responses for ${m.meal_type.toUpperCase()}!`, 'error');
        } else if (m.status === 'closed') {
          showToast(`🔒 Mess Admin has CLOSED responses early for ${m.meal_type.toUpperCase()}!`, 'error');
        } else if (m.status === 'open') {
          showToast(`▶️ Mess Admin has REOPENED responses for ${m.meal_type.toUpperCase()}!`, 'success');
        }
      }
      lastKnownMealStatuses[m.id] = m.status;

      // Update UI elements based on live status
      if (m.is_paused) {
        if (countdownWrapper) {
          countdownWrapper.innerHTML = `
            <span id="deadline-pill-${m.id}" class="status-badge" style="background: #fef3c7; color: #b45309; border: 1px solid #fde68a; font-weight: 700; font-size: 0.8rem;">
              ⏸️ Responses Paused
            </span>
          `;
        }
        if (lockedBanner) {
          lockedBanner.style.display = 'block';
          lockedBanner.style.background = '#fffbeb';
          lockedBanner.style.color = '#b45309';
          lockedBanner.style.borderColor = '#fde68a';
          lockedBanner.innerText = '⏸️ Responses have been temporarily paused by Mess Admin. Kitchen is auditing live counts.';
        }
        if (responseContainer) {
          responseContainer.style.display = 'none';
        }
      } else if (m.is_closed_early || (m.status === 'closed' && !m.is_past_deadline)) {
        if (countdownWrapper) {
          countdownWrapper.innerHTML = `
            <span id="deadline-pill-${m.id}" class="status-badge badge-closed" style="font-weight: 700; font-size: 0.8rem;">
              🔒 Closed Early
            </span>
          `;
        }
        if (lockedBanner) {
          lockedBanner.style.display = 'block';
          lockedBanner.style.background = '#f1f5f9';
          lockedBanner.style.color = '#64748b';
          lockedBanner.style.borderColor = '#e2e8f0';
          lockedBanner.innerText = '🔒 Response window was closed early by Mess Admin. Kitchen preparations are now locked.';
        }
        if (responseContainer) {
          responseContainer.style.display = 'none';
        }
      } else if (m.is_past_deadline) {
        if (countdownWrapper) {
          countdownWrapper.innerHTML = `
            <span id="deadline-pill-${m.id}" class="status-badge badge-closed" style="font-weight: 700; font-size: 0.8rem;">
              🔒 Closed
            </span>
          `;
        }
        if (lockedBanner) {
          lockedBanner.style.display = 'block';
          lockedBanner.style.background = '#f1f5f9';
          lockedBanner.style.color = '#64748b';
          lockedBanner.style.borderColor = '#e2e8f0';
          lockedBanner.innerText = `Response deadline (${m.deadline_display}) has passed. Meal preparations are locked.`;
        }
        if (responseContainer) {
          responseContainer.style.display = 'none';
        }
      } else if (m.status === 'open') {
        // Active and open!
        if (lockedBanner) {
          lockedBanner.style.display = 'none';
        }
        if (responseContainer) {
          responseContainer.style.display = 'block';
        }
        if (countdownWrapper && !countdownWrapper.querySelector('[data-deadline]')) {
          countdownWrapper.innerHTML = `
            <span id="deadline-pill-${m.id}" class="status-badge badge-open" data-deadline="${m.iso_deadline}" style="font-weight: 700; font-size: 0.8rem;">
              ⏳ Counting down...
            </span>
          `;
        }
      }
    });
  } catch (e) {
    // Ignore transient network errors
  }
}

document.addEventListener('DOMContentLoaded', () => {
  updateDeadlineCountdowns();
  setInterval(updateDeadlineCountdowns, 1000); // Ticks every second
  
  // Real-time synchronization for student side (detects pause / close early / reopen)
  syncStudentMealStatuses();
  setInterval(syncStudentMealStatuses, 3000); // Polls every 3 seconds
});

