document.addEventListener("DOMContentLoaded", function () {
    const filterSelect = document.getElementById("customer-filter-by");
    if (!filterSelect) {
        return;
    }

    const form = filterSelect.form;
    const groups = Array.from(
        form.querySelectorAll("[data-customer-filter]")
    );
    const help = document.getElementById("customer-filter-help");
    const messages = {
        age: "Enter an age range (at least one boundary).",
        gender: "Choose the client gender to match.",
        client_type: "Choose new clients or returning clients.",
        orders: "Enter an order-count range (at least one boundary).",
        spend: "Enter a spend range (at least one boundary)."
    };

    function showSelectedFilter(clearPrevious) {
        const selected = filterSelect.value;
        groups.forEach(function (group) {
            const isSelected = group.dataset.customerFilter === selected;
            if (clearPrevious && !isSelected) {
                group.querySelectorAll("input, select").forEach(function (input) {
                    input.value = "";
                });
            }
            group.hidden = !isSelected;
        });
        help.textContent = messages[selected]
            || "Choose a filter to enter matching client details.";
    }

    filterSelect.addEventListener("change", function () {
        filterSelect.setCustomValidity("");
        showSelectedFilter(true);
        const active = groups.find(function (group) {
            return group.dataset.customerFilter === filterSelect.value;
        });
        if (active) {
            const firstInput = active.querySelector("input, select");
            if (firstInput) {
                firstInput.focus();
            }
        }
    });

    form.addEventListener("submit", function (event) {
        const selected = filterSelect.value;
        const group = groups.find(function (item) {
            return item.dataset.customerFilter === selected;
        });
        if (!group) {
            filterSelect.setCustomValidity("");
            return;
        }
        const values = Array.from(
            group.querySelectorAll("input, select")
        ).map(function (input) {
            return input.value.trim();
        });
        if (!values.some(Boolean)) {
            filterSelect.setCustomValidity(messages[selected]);
            filterSelect.reportValidity();
            event.preventDefault();
            return;
        }
        filterSelect.setCustomValidity("");
    });

    filterSelect.addEventListener("input", function () {
        filterSelect.setCustomValidity("");
    });
});
