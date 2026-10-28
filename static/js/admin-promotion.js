document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("promotion-form");
    const discountType = form.querySelector('[name="discount_type"]');
    const discountValue = document.getElementById("discount-value");
    const discountLabel = document.getElementById("discount-value-label");
    const targetScope = document.getElementById("target-scope");
    const categorySelection = document.getElementById("category-selection");
    const productSelection = document.getElementById("product-selection");
    const featureToggles = form.querySelectorAll("[data-feature-toggle]");

    function updateDiscountFields() {
        const isPercent = discountType.value === "percent";
        discountLabel.textContent = isPercent
            ? "Discount percentage (%)"
            : "Discount amount (₹)";
        discountValue.max = isPercent ? "100" : "";
        discountValue.step = "1";
    }

    function updateTargetFields() {
        const categoriesSelected = targetScope.value === "categories";
        const productsSelected = targetScope.value === "products";
        categorySelection.hidden = !categoriesSelected;
        productSelection.hidden = !productsSelected;
        [
            [categorySelection, "category_ids", categoriesSelected],
            [productSelection, "product_ids", productsSelected],
        ].forEach(function ([selection, fieldName, isSelected]) {
            const checkboxes = selection.querySelectorAll(
                'input[name="' + fieldName + '"]'
            );
            checkboxes.forEach(function (checkbox) {
                checkbox.required = isSelected && checkboxes.length === 1;
            });
        });
    }

    function updateAudienceFields() {
        featureToggles.forEach(function (toggle) {
            const fields = form.querySelector(
                '[data-feature-fields="' + toggle.value + '"]'
            );
            if (fields) {
                fields.hidden = !toggle.checked;
                fields.querySelectorAll("[data-required-when-visible]").forEach(
                    function (input) {
                        input.required = toggle.checked;
                    }
                );
            }
        });
    }

    discountType.addEventListener("change", updateDiscountFields);
    targetScope.addEventListener("change", updateTargetFields);
    featureToggles.forEach(function (toggle) {
        toggle.addEventListener("change", updateAudienceFields);
    });
    updateDiscountFields();
    updateTargetFields();
    updateAudienceFields();
});
