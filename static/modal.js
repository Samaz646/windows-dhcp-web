// modal.js
document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('openReservationModalBtn');
    const modalEl = document.getElementById('addReservationModal');

    if (!btn || !modalEl) return;

    const modal = new bootstrap.Modal(modalEl);

    // Button öffnet Modal
    btn.addEventListener('click', function () {
        let selected = document.querySelector('input.select-lease:checked'); // leases.html

        // Fallback für seen_devices.html
        if (!selected) {
            selected = document.querySelector('tr.table-active');
        }

        document.getElementById('macInput').value = selected?.dataset.mac || '';
        document.getElementById('ipInput').value = selected?.dataset.ip || '';
        document.getElementById('hostnameInput').value = selected?.dataset.hostname || '';

        modal.show();
    });

    // Modal schließen
    modalEl.querySelectorAll('[data-bs-dismiss="modal"]').forEach(btn => {
        btn.addEventListener('click', function () {
            modal.hide();
        });
    });

    // Prefill durch Flask (Fehler oder Werte)
    if (typeof prefillData !== "undefined" && (prefillData.mac || prefillData.ip || prefillData.hostname || prefillData.error)) {
        document.getElementById('macInput').value = prefillData.mac || '';
        document.getElementById('ipInput').value = prefillData.ip || '';
        document.getElementById('hostnameInput').value = prefillData.hostname || '';
        modal.show();
    }
});
