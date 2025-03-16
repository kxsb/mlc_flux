// Variables globales pour stocker les différentes versions des données
let rawData = null;
let standardizedData = null;
let newTableData = null;
let filteredStandardizedData = null;

// Gestion du toggle du panneau latéral
document.getElementById('toggleSidebar').addEventListener('click', function() {
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.getElementById('mainContent');
  sidebar.classList.toggle('hidden');
  
  if (sidebar.classList.contains('hidden')) {
    mainContent.classList.add('full-width');
    this.textContent = "Afficher le panneau";
  } else {
    mainContent.classList.remove('full-width');
    this.textContent = "Masquer le panneau";
  }
});

// Lorsqu'un filtre est sélectionné (tableau ou statistiques), on met à jour l'affichage
document.querySelectorAll('input[name="dataView"]').forEach(radio => {
  radio.addEventListener('change', updateDisplay);
});

// Bouton "Sélectionner un jeu de données"
document.getElementById('selectDatasetButton').addEventListener('click', function() {
  fetch('/datasets')
    .then(resp => resp.json())
    .then(fileList => {
      if (!fileList || fileList.length === 0) {
        alert("Aucun jeu de données trouvé.");
        return;
      }
      
      let message = "Liste des jeux de données disponibles :\n";
      fileList.forEach((filename, index) => {
        message += `${index + 1}. ${filename}\n`;
      });
      message += "\nEntrez le numéro du fichier à charger :";
      
      const choice = prompt(message);
      const choiceIndex = parseInt(choice, 10) - 1;
      
      if (isNaN(choiceIndex) || choiceIndex < 0 || choiceIndex >= fileList.length) {
        alert("Sélection invalide.");
        return;
      }
      
      const selectedFile = fileList[choiceIndex];
      
      // Charger les données standardisées
      fetch(`/data/${selectedFile}`)
        .then(resp => resp.json())
        .then(jsonData => {
          standardizedData = jsonData;
          // Réinitialiser le filtrage à l'import d'un nouveau fichier
          filteredStandardizedData = null;
          updateDisplay();
        })
        .catch(err => console.error("Erreur lors du chargement des données standardisées :", err));
      
      // Charger également le nouveau tableau agrégé
      fetch(`/newtable/${selectedFile}`)
        .then(resp => resp.json())
        .then(newTableJson => {
          newTableData = newTableJson;
          updateDisplay();
        })
        .catch(err => console.error("Erreur lors du chargement du nouveau tableau :", err));
    })
    .catch(err => console.error("Erreur lors de la récupération de la liste des jeux de données :", err));
});

// Gestion de l'import via fichier XLSX
document.getElementById('importButton').addEventListener('click', function() {
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = '.xlsx';
  fileInput.style.display = 'none';

  fileInput.addEventListener('change', function(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Lecture locale pour récupérer les données brutes
    const reader = new FileReader();
    reader.onload = function(e) {
      const data = new Uint8Array(e.target.result);
      const workbook = XLSX.read(data, { type: 'array' });
      const sheetName = workbook.SheetNames[0];
      rawData = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName], { header: 1 });
      console.log("Raw data:", rawData);
      if (document.querySelector('input[name="dataView"]:checked').value === 'raw') {
        displayTable(rawData);
      }
    };
    reader.readAsArrayBuffer(file);

    // Envoi du fichier au serveur pour transformation
    const formData = new FormData();
    formData.append('file', file);

    fetch('/upload', {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.output) {
        alert("Fichier transformé créé : " + data.output);
        fetch(`/data/${data.output}`)
          .then(resp => resp.json())
          .then(jsonData => {
            standardizedData = jsonData;
            filteredStandardizedData = null; // réinitialiser le filtrage
            fetch(`/newtable/${data.output}`)
              .then(resp => resp.json())
              .then(newTableJson => {
                newTableData = newTableJson;
                updateDisplay();
              })
              .catch(err => console.error("Erreur lors de la récupération du nouveau tableau :", err));
          })
          .catch(err => console.error("Erreur lors de la récupération des données standardisées :", err));
      } else if (data.error) {
        alert("Erreur : " + data.error);
      }
    })
    .catch(error => {
      console.error('Erreur lors de l\'upload :', error);
      alert("Une erreur est survenue lors de l'import.");
    });
  });

  document.body.appendChild(fileInput);
  fileInput.click();
});

// Appliquer le filtre du panneau de contrôle pour ignorer les transactions "coffre"
document.getElementById('applyFilter').addEventListener('click', function() {
  const ignoreExp = document.getElementById('ignoreCoffreExpediteur').checked;
  const ignoreDest = document.getElementById('ignoreCoffreDestinataire').checked;
  
  if (!standardizedData) {
    alert("Pas de données standardisées à filtrer.");
    return;
  }
  
  // Créer une version filtrée sans écraser l'original
  let filteredData = [standardizedData[0]]; // l'en-tête
  for (let i = 1; i < standardizedData.length; i++) {
    let row = standardizedData[i];
    // Supposons que "Type_Expéditeur" est à l'index 6 et "Type_Destinataire" à l'index 7
    let typeExp = row[6];
    let typeDest = row[7];
    
    if (ignoreExp && typeExp === "C") continue;
    if (ignoreDest && typeDest === "C") continue;
    
    filteredData.push(row);
  }
  
  filteredStandardizedData = filteredData;
  updateDisplay();
});

// Mise à jour de l'affichage en fonction du filtre sélectionné
function updateDisplay() {
  const view = document.querySelector('input[name="dataView"]:checked').value;
  // Utiliser la version filtrée si disponible, sinon l'originale
  let dataToDisplay = filteredStandardizedData || standardizedData;
  
  if (view === 'raw') {
    if (rawData) {
      displayTable(rawData);
    } else {
      document.getElementById('tableContainer').innerHTML = "<p>Données brutes indisponibles.</p>";
    }
  } else if (view === 'standardized') {
    if (dataToDisplay) {
      displayTable(dataToDisplay);
    }
  } else if (view === 'new') {
    if (newTableData) {
      displayTable(newTableData);
    }
  } else if (view === 'stats') {
    displayStats(dataToDisplay);
  }
}

// Affichage d'un tableau HTML dans le conteneur
function displayTable(tableData) {
  const container = document.getElementById('tableContainer');
  const table = document.createElement('table');
  
  if (Array.isArray(tableData) && Array.isArray(tableData[0])) {
    console.log("Nombre total de lignes :", tableData.length);
    const headerLength = tableData[0].length;
    console.log("Nombre de colonnes attendu :", headerLength);
    
    tableData.forEach((row, rowIndex) => {
      if (row.length !== headerLength) {
        console.warn(`La ligne ${rowIndex} a ${row.length} colonnes au lieu de ${headerLength}:`, row);
      }
      const tr = document.createElement('tr');
      row.forEach(cell => {
        const cellElement = rowIndex === 0 ? document.createElement('th') : document.createElement('td');
        cellElement.textContent = cell;
        tr.appendChild(cellElement);
      });
      table.appendChild(tr);
    });
  }
  else if (Array.isArray(tableData) && typeof tableData[0] === 'object') {
    const headerKeys = Object.keys(tableData[0]);
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerKeys.forEach(key => {
      const th = document.createElement('th');
      th.textContent = key;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    const tbody = document.createElement('tbody');
    tableData.forEach((item, index) => {
      const tr = document.createElement('tr');
      headerKeys.forEach(key => {
        const td = document.createElement('td');
        if (!(key in item)) {
          console.warn(`L'objet à l'index ${index} n'a pas la clé "${key}".`, item);
        }
        td.textContent = item[key] || '';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
  }
  
  container.innerHTML = "";
  container.appendChild(table);
  addSortingToTable(table);
}

// Fonction qui ajoute des écouteurs aux <th> pour trier les colonnes
function addSortingToTable(table) {
  const thead = table.querySelector('thead');
  if (!thead) return;
  const headerCells = thead.querySelectorAll('th');
  headerCells.forEach((th, index) => {
    th.style.cursor = "pointer";
    th.addEventListener("click", function() {
      let currentOrder = th.getAttribute("data-order") || "asc";
      let newOrder = currentOrder === "asc" ? "desc" : "asc";
      th.setAttribute("data-order", newOrder);
      
      const tbody = table.querySelector("tbody");
      if (!tbody) return;
      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {
         let aText = a.children[index].textContent.trim();
         let bText = b.children[index].textContent.trim();
         let aNum = parseFloat(aText);
         let bNum = parseFloat(bText);
         let isNumeric = !isNaN(aNum) && !isNaN(bNum);
         if (isNumeric) {
           return newOrder === "asc" ? aNum - bNum : bNum - aNum;
         } else {
           if (aText < bText) return newOrder === "asc" ? -1 : 1;
           if (aText > bText) return newOrder === "asc" ? 1 : -1;
           return 0;
         }
      });
      rows.forEach(row => tbody.appendChild(row));
    });
  });
}
