// SmartMess Analytics Charts Integration

function initAnalyticsCharts(statsData) {
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js not loaded');
    return;
  }

  // 1. Expected vs Actual Servings Chart
  const expectedVsActualCtx = document.getElementById('expectedVsActualChart');
  if (expectedVsActualCtx && statsData.consumption_history) {
    const labels = statsData.consumption_history.map(item => `${item.meal_date.substring(5)} (${item.meal_type[0].toUpperCase()})`);
    const preparedData = statsData.consumption_history.map(item => item.food_prepared_portions);
    const eatersData = statsData.consumption_history.map(item => item.actual_eaters);

    new Chart(expectedVsActualCtx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Portions Prepared (with Buffer)',
            data: preparedData,
            backgroundColor: '#059669',
            borderRadius: 6
          },
          {
            label: 'Actual People Who Ate',
            data: eatersData,
            backgroundColor: '#0284c7',
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Servings / Portions' } }
        }
      }
    });
  }

  // 2. Food Wastage Trend Chart
  const wastageTrendCtx = document.getElementById('wastageTrendChart');
  if (wastageTrendCtx && statsData.daily_trend) {
    const dates = statsData.daily_trend.map(d => d.meal_date.substring(5));
    const wastedPortions = statsData.daily_trend.map(d => d.daily_wasted);

    new Chart(wastageTrendCtx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [{
          label: 'Daily Wasted Portions',
          data: wastedPortions,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.35,
          borderWidth: 3,
          pointBackgroundColor: '#ef4444',
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' }
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Portions Left Over' } }
        }
      }
    });
  }

  // 3. Meal-wise Participation Donut / Bar
  const mealTypeCtx = document.getElementById('mealTypeChart');
  if (mealTypeCtx && statsData.meal_type_stats) {
    const mealLabels = statsData.meal_type_stats.map(m => m.meal_type.toUpperCase());
    const eatersAvg = statsData.meal_type_stats.map(m => m.avg_eaters);

    new Chart(mealTypeCtx, {
      type: 'doughnut',
      data: {
        labels: mealLabels,
        datasets: [{
          data: eatersAvg,
          backgroundColor: ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  }
}
