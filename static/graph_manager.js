// graph_manager.js

// Fonction auxiliaire pour obtenir la date du lundi de la semaine d'une date donnée
function getWeekStart(date) {
  let d = new Date(date);
  let day = d.getDay(); // 0 = dimanche, 1 = lundi, etc.
  let diff = d.getDate() - (day === 0 ? 6 : day - 1);
  let weekStart = new Date(d.setDate(diff));
  return weekStart.toISOString().slice(0, 10);
}

function displayStats(standardizedData) {
  // Vérifier que standardizedData est disponible
  if (!standardizedData) {
    document.getElementById('tableContainer').innerHTML = "<p>Données indisponibles.</p>";
    return;
  }
  
  // ---------------------------
  // Extraction commune des dates
  let dates = [];
  for (let i = 1; i < standardizedData.length; i++) {
    let row = standardizedData[i];
    let dateStr = row[0]; // Supposons que la date est en 1ère colonne
    let date = new Date(dateStr);
    if (!isNaN(date)) {
      dates.push(date.toISOString().slice(0, 10));
    }
  }
  
  // ---------------------------
  // Graphique 1 : Nombre de transactions par jour
  let counts = {};
  dates.forEach(d => {
    counts[d] = (counts[d] || 0) + 1;
  });
  let sortedDates = Object.keys(counts).sort();
  let transactionCounts = sortedDates.map(date => counts[date]);
  
  // ---------------------------
  // Graphique 2 : Moyenne hebdomadaire des montants
  // On suppose que la colonne "Montant" est à l'index 1
  let weeklyData = {}; // clé : date du lundi, valeur : { sum, count }
  for (let i = 1; i < standardizedData.length; i++) {
    let row = standardizedData[i];
    let dateStr = row[0];
    let montant = parseFloat(row[1]); // adapter si nécessaire
    let date = new Date(dateStr);
    if (!isNaN(date) && !isNaN(montant)) {
      let weekStart = getWeekStart(date);
      if (!weeklyData[weekStart]) {
        weeklyData[weekStart] = { sum: 0, count: 0 };
      }
      weeklyData[weekStart].sum += montant;
      weeklyData[weekStart].count += 1;
    }
  }
  let sortedWeeks = Object.keys(weeklyData).sort();
  let weeklyAvg = sortedWeeks.map(week => weeklyData[week].sum / weeklyData[week].count);
  
  // ---------------------------
  // Graphique 3 : Transactions par heure de la journée
  let hourlyCounts = {};
  for (let h = 0; h < 24; h++) {
    hourlyCounts[h] = 0;
  }
  for (let i = 1; i < standardizedData.length; i++) {
    let row = standardizedData[i];
    let dateStr = row[0];
    let date = new Date(dateStr);
    if (!isNaN(date)) {
      let hour = date.getHours();
      hourlyCounts[hour] = (hourlyCounts[hour] || 0) + 1;
    }
  }
  let hours = Object.keys(hourlyCounts).sort((a, b) => a - b);
  let countsPerHour = hours.map(hour => hourlyCounts[hour]);
  
  // ---------------------------
  // Graphique 4 : Transactions par jour de la semaine
  // On regroupe par jour (0 = dimanche, 1 = lundi, …)
  let weekdayCounts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0};
  for (let i = 1; i < standardizedData.length; i++) {
    let row = standardizedData[i];
    let dateStr = row[0];
    let date = new Date(dateStr);
    if (!isNaN(date)) {
      let day = date.getDay();
      weekdayCounts[day] = (weekdayCounts[day] || 0) + 1;
    }
  }
  // Pour afficher de lundi à dimanche, on réorganise : [1,2,3,4,5,6,0]
  let orderedDays = [1, 2, 3, 4, 5, 6, 0];
  let dayNames = {0: "Dimanche", 1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi", 6: "Samedi"};
  let weekdayLabels = orderedDays.map(d => dayNames[d]);
  let weekdayTransactionCounts = orderedDays.map(d => weekdayCounts[d]);
  
  // ---------------------------
  // Graphique 5 : Volume cumulé des transactions
  let transactions = [];
  for (let i = 1; i < standardizedData.length; i++) {
    let row = standardizedData[i];
    let dateStr = row[0];
    let montant = parseFloat(row[1]);
    let date = new Date(dateStr);
    if (!isNaN(date) && !isNaN(montant)) {
      transactions.push({ date: date, montant: montant });
    }
  }
  transactions.sort((a, b) => a.date - b.date);
  let cumulativeVolume = [];
  let cumulativeSum = 0;
  let cumulativeDates = [];
  transactions.forEach(tx => {
    cumulativeSum += tx.montant;
    cumulativeDates.push(tx.date.toISOString().slice(0, 10));
    cumulativeVolume.push(cumulativeSum);
  });
  
  // ---------------------------
  // Insertion des canvas pour les 5 graphiques dans le container
  const container = document.getElementById('tableContainer');
  container.innerHTML = `
    <canvas id="statsChart" style="max-width: 100%; margin-bottom: 30px;"></canvas>
    <canvas id="weeklyAvgChart" style="max-width: 100%; margin-bottom: 30px;"></canvas>
    <canvas id="hourlyChart" style="max-width: 100%; margin-bottom: 30px;"></canvas>
    <canvas id="weekdayChart" style="max-width: 100%; margin-bottom: 30px;"></canvas>
    <canvas id="cumulativeChart" style="max-width: 100%;"></canvas>
  `;
  
  // ---------------------------
  // Création des graphiques avec Chart.js
  
  // Graphique 1 : Nombre de transactions par jour
  const ctx1 = document.getElementById('statsChart').getContext('2d');
  new Chart(ctx1, {
    type: 'line',
    data: {
      labels: sortedDates,
      datasets: [{
        label: 'Nombre de transactions par jour',
        data: transactionCounts,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        fill: true,
        tension: 0.1
      }]
    },
    options: {
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          title: { display: true, text: 'Date' }
        },
        y: { title: { display: true, text: 'Transactions' }, beginAtZero: true }
      }
    }
  });
  
  // Graphique 2 : Moyenne hebdomadaire des montants
  const ctx2 = document.getElementById('weeklyAvgChart').getContext('2d');
  new Chart(ctx2, {
    type: 'line',
    data: {
      labels: sortedWeeks,
      datasets: [{
        label: 'Volume moyen de transaction (hebdomadaire)',
        data: weeklyAvg,
        borderColor: 'rgba(153, 102, 255, 1)',
        backgroundColor: 'rgba(153, 102, 255, 0.2)',
        fill: true,
        tension: 0.1
      }]
    },
    options: {
      scales: {
        x: {
          type: 'time',
          time: { unit: 'week' },
          title: { display: true, text: 'Semaine (début)' }
        },
        y: { title: { display: true, text: 'Volume moyen' }, beginAtZero: true }
      }
    }
  });
  
  // Graphique 3 : Transactions par heure de la journée
  const ctx3 = document.getElementById('hourlyChart').getContext('2d');
  new Chart(ctx3, {
    type: 'bar',
    data: {
      labels: hours.map(h => h + "h"),
      datasets: [{
        label: 'Transactions par heure',
        data: countsPerHour,
        backgroundColor: 'rgba(255, 159, 64, 0.2)',
        borderColor: 'rgba(255, 159, 64, 1)',
        borderWidth: 1
      }]
    },
    options: {
      scales: {
        x: { title: { display: true, text: 'Heure de la journée' } },
        y: { beginAtZero: true, title: { display: true, text: 'Nombre de transactions' } }
      }
    }
  });
  
  // Graphique 4 : Transactions par jour de la semaine
  const ctx4 = document.getElementById('weekdayChart').getContext('2d');
  new Chart(ctx4, {
    type: 'bar',
    data: {
      labels: weekdayLabels,
      datasets: [{
        label: 'Transactions par jour de la semaine',
        data: weekdayTransactionCounts,
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1
      }]
    },
    options: {
      scales: {
        x: { title: { display: true, text: 'Jour de la semaine' } },
        y: { beginAtZero: true, title: { display: true, text: 'Nombre de transactions' } }
      }
    }
  });
  
  // Graphique 5 : Volume cumulé des transactions
  const ctx5 = document.getElementById('cumulativeChart').getContext('2d');
  new Chart(ctx5, {
    type: 'line',
    data: {
      labels: cumulativeDates,
      datasets: [{
        label: 'Volume cumulé des transactions',
        data: cumulativeVolume,
        borderColor: 'rgba(255, 99, 132, 1)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        fill: true,
        tension: 0.1
      }]
    },
    options: {
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day' },
          title: { display: true, text: 'Date' }
        },
        y: { title: { display: true, text: 'Volume cumulé' }, beginAtZero: true }
      }
    }
  });
}
