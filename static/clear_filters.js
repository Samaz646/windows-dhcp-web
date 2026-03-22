function clearFilters() {
    const form = document.querySelector("form[method='get']");
    if (!form) return;

    // Felder explizit leeren
    form.querySelectorAll('input').forEach(input => input.value = '');

    // Tabelle dynamisch neu laden
    fetch(window.location.pathname)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newTbody = doc.querySelector('table tbody');
            const oldTbody = document.querySelector('table tbody');
            if (newTbody && oldTbody) {
                oldTbody.replaceWith(newTbody);
            }
        })
        .catch(err => console.error('Fehler beim Neuladen der Tabelle:', err));
}
