// SmartMess Admin Interactive Real-time Controls

let currentBuffer = 10.0;
let currentMode = 'standard';
let selectedHostelId = null;

function setBuffer(percent, buttonEl) {
  currentBuffer = parseFloat(percent);
  
  // Highlight active pill
  document.querySelectorAll('.buffer-pill').forEach(btn => btn.classList.remove('active'));
  if (buttonEl) buttonEl.classList.add('active');

  const customInput = document.getElementById('custom-buffer-input');
  if (customInput && [5, 10, 15].includes(currentBuffer)) {
    customInput.value = '';
  }

  saveSettingsAndUpdate({ buffer_percentage: currentBuffer });
}

function setCustomBuffer(val) {
  const num = parseFloat(val);
  if (!isNaN(num) && num >= 0 && num <= 50) {
    currentBuffer = num;
    document.querySelectorAll('.buffer-pill').forEach(btn => btn.classList.remove('active'));
    saveSettingsAndUpdate({ buffer_percentage: currentBuffer });
  }
}

function setMode(modeName, buttonEl) {
  currentMode = modeName;
  document.querySelectorAll('.mode-pill').forEach(btn => btn.classList.remove('active'));
  if (buttonEl) buttonEl.classList.add('active');

  const modeBadge = document.getElementById('active-mode-badge');
  if (modeBadge) {
    modeBadge.textContent = modeName.toUpperCase() + ' MODE';
  }

  saveSettingsAndUpdate({ estimation_mode: currentMode });
}

async function saveSettingsAndUpdate(payload) {
  const formData = new FormData();
  if (payload.buffer_percentage !== undefined) {
    formData.append('buffer_percentage', payload.buffer_percentage);
  }
  if (payload.estimation_mode !== undefined) {
    formData.append('estimation_mode', payload.estimation_mode);
  }

  try {
    const res = await fetch('/admin/api/settings', {
      method: 'POST',
      body: formData
    });
    if (res.ok) {
      // Trigger instant stats refresh
      refreshLiveStats();
    }
  } catch (err) {
    console.error('Failed to update settings', err);
  }
}

async function refreshLiveStats() {
  const hostelSelect = document.getElementById('admin-hostel-filter');
  const hId = hostelSelect ? hostelSelect.value : '';

  const url = `/api/realtime/meal-stats?buffer_percent=${currentBuffer}&mode=${currentMode}${hId ? '&hostel_id=' + hId : ''}`;

  try {
    const res = await fetch(url);
    if (!res.ok) return;

    const data = await res.json();
    let totalRecommendedSum = 0;

    data.meals.forEach(m => {
      const card = document.getElementById(`admin-meal-card-${m.id}`);
      if (!card) return;

      const willEatEl = document.getElementById(`count-will-eat-${m.id}`);
      const notEatingEl = document.getElementById(`count-not-eating-${m.id}`);
      const noResponseEl = document.getElementById(`count-no-response-${m.id}`);
      const recServingsEl = document.getElementById(`rec-servings-${m.id}`);
      const formulaEl = document.getElementById(`formula-box-${m.id}`);
      const respRateEl = document.getElementById(`resp-rate-${m.id}`);

      if (willEatEl) willEatEl.innerText = m.stats.confirmed_eating;
      if (notEatingEl) notEatingEl.innerText = m.stats.confirmed_not_eating;
      if (noResponseEl) noResponseEl.innerText = m.stats.no_response;
      if (recServingsEl) recServingsEl.innerText = m.stats.recommended_servings;
      if (formulaEl) formulaEl.innerText = m.stats.formula_display;
      if (respRateEl) respRateEl.innerText = m.stats.response_rate + '%';

      totalRecommendedSum += m.stats.recommended_servings;
    });

    const totalSummaryEl = document.getElementById('total-recommended-sum');
    if (totalSummaryEl) {
      totalSummaryEl.innerText = totalRecommendedSum;
    }

  } catch (err) {
    console.warn('Realtime poll error:', err);
  }
}

// Trigger in-app notification reminder broadcast
async function broadcastReminder(mealId, btnElement) {
  if (btnElement) {
    btnElement.disabled = true;
    btnElement.innerHTML = 'Sending...';
  }

  try {
    const res = await fetch(`/admin/meals/${mealId}/notify`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Reminder sent to residents!', 'success');
    } else {
      showToast('Could not send notification.', 'error');
    }
  } catch (err) {
    showToast('Failed to broadcast reminder.', 'error');
  } finally {
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.innerHTML = '📢 Notify Residents';
    }
  }
}

// Auto poll every 3.5 seconds for real-time dashboard updates
document.addEventListener('DOMContentLoaded', () => {
  // Read initial buffer and mode from DOM if set
  const initialBufferEl = document.querySelector('.buffer-pill.active');
  if (initialBufferEl) {
    currentBuffer = parseFloat(initialBufferEl.getAttribute('data-buffer') || 10);
  }
  const initialModeEl = document.querySelector('.mode-pill.active');
  if (initialModeEl) {
    currentMode = initialModeEl.getAttribute('data-mode') || 'standard';
  }

  if (document.getElementById('admin-live-dashboard')) {
    setInterval(refreshLiveStats, 3500);
  }
});
