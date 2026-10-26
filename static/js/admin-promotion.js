document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("promotion-form");
    const discountType = form.querySelector('[name="discount_type"]');
    const discountValue = document.getElementById("discount-value");
    const discountLabel = document.getElementById("discount-value-label");
    const categoryScope = document.getElementById("category-scope");
    const categorySelection = document.getElementById("category-selection");
    const featureToggles = form.querySelectorAll("[data-feature-toggle]");

    function updateDiscountFields() {
        const isPercent = discountType.value === "percent";
        discountLabel.textContent = isPercent
            ? "Discount percentage (%)"
            : "Discount amount (₹)";
        discountValue.max = isPercent ? "100" : "";
        discountValue.step = "1";
    }

    function updateCategoryFields() {
        const specific = categoryScope.value === "specific";
        categorySelection.hidden = !specific;
        categorySelection.querySelectorAll('input[name="category_ids"]').forEach(
            function (checkbox) {
                checkbox.required = specific
                    && categorySelection.querySelectorAll(
                        'input[name="category_ids"]'
                    ).length === 1;
            }
        );
    }

    function updateAudienceFields() {
        featureToggles.forEach(function (toggle) {
            const fields = form.querySelector(
                '[data-feature-fields="' + toggle.value + '"]'
            );
            if (fields) {
                fields.hidden = !toggle.checked;
            }
        });
    }

    discountType.addEventListener("change", updateDiscountFields);
    categoryScope.addEventListener("change", updateCategoryFields);
    featureToggles.forEach(function (toggle) {
        toggle.addEventListener("change", updateAudienceFields);
    });
    updateDiscountFields();
    updateCategoryFields();
    updateAudienceFields();
});
