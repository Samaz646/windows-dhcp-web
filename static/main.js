// main.js
document.addEventListener('DOMContentLoaded', function () {
    const rows = document.querySelectorAll("table tbody tr");

    rows.forEach(row => {
        row.addEventListener("click", function () {
            // vorherige Auswahl entfernen
            rows.forEach(r => r.classList.remove("table-active"));

            // aktuelle Zeile markieren
            row.classList.add("table-active");

            // Daten-Attribute für Modal vorbereiten
            const cells = row.querySelectorAll("td");
            if (cells.length >= 3) {
                row.dataset.ip = cells[0].textContent.trim();
                row.dataset.mac = cells[1].textContent.trim();
                row.dataset.hostname = cells[2].textContent.trim();
            }
        });
    });
});
