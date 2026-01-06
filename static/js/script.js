async function generatePlan() {
    const btn = document.getElementById('btnGenerisi');
    const results = document.getElementById('results');
    const loading = document.getElementById('loading');

    // UI State
    btn.disabled = true;
    loading.classList.remove('d-none');
    results.classList.add('d-none');

    const data = {
        grad: document.getElementById('grad').value,
        voda: document.getElementById('voda').value,
        riba: document.getElementById('riba').value,
        brendovi: ["Svi brendovi"], // Možeš dodati multiselect
        iskustvo: "Srednje",
        budzet: document.querySelector('input[name="budzet"]:checked').value
    };

    try {
        const response = await fetch('/generate-plan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        const result = await response.json();

        // Popunjavanje rezultata
        document.getElementById('taktika').innerText = result.taktika;
        document.getElementById('lokacije').innerText = result.mesta;
        
        let listHtml = '';
        result.lista.forEach(item => {
            listHtml += `
                <label class="list-group-item d-flex gap-2">
                    <input class="form-check-input flex-shrink-0" type="checkbox" value="">
                    <span>${item}</span>
                </label>`;
        });
        document.getElementById('shoppingItems').innerHTML = listHtml;

        results.classList.remove('d-none');
    } catch (error) {
        alert("Greška pri generisanju plana.");
    } finally {
        loading.classList.add('d-none');
        btn.disabled = false;
    }
}

function copyToClipboard() {
    let items = Array.from(document.querySelectorAll('#shoppingItems input:checked'))
                     .map(i => i.nextElementSibling.innerText);
    let text = "Moj Feeder Spisak:\n" + items.join("\n");
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
}