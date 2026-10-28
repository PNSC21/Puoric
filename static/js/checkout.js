document.addEventListener("DOMContentLoaded", function () {
    const addresses = document.querySelectorAll('input[name="address_id"]');
    const shippingLabel = document.getElementById("shipping-label");
    const shippingAmount = document.getElementById("shipping-amount");
    const freeShippingNote = document.getElementById("free-shipping-note");
    const total = document.getElementById("checkout-total");

    if (!addresses.length || !shippingLabel || !shippingAmount || !total) {
        return;
    }

    const formatter = new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        minimumFractionDigits: 2,
    });

    function updateShipping() {
        const address = document.querySelector('input[name="address_id"]:checked');
        if (!address) {
            return;
        }

        const amount = Number(address.dataset.shippingAmount);
        const merchandiseTotal = Number(total.dataset.merchandiseTotal);
        shippingLabel.textContent = address.dataset.shippingLabel;
        shippingAmount.textContent = formatter.format(amount);
        total.textContent = formatter.format(merchandiseTotal + amount);
        if (freeShippingNote) {
            const threshold = address.dataset.freeShippingThreshold;
            freeShippingNote.textContent = address.dataset.freeShipping === "true"
                ? "Free shipping applied."
                : threshold
                    ? "Free shipping on merchandise orders of "
                        + formatter.format(Number(threshold)) + " or more."
                    : "";
        }
    }

    addresses.forEach(function (address) {
        address.addEventListener("change", updateShipping);
    });
    updateShipping();
});
