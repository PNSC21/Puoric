document.addEventListener("DOMContentLoaded", function () {
    const categorySelect = document.getElementById("product-category");
    const tagsByCategory = JSON.parse(
        document.getElementById("category-characteristics").textContent
    );
    const variantTypesByCategory = JSON.parse(
        document.getElementById("category-variant-types").textContent
    );
    const characteristicRows = document.getElementById("characteristic-rows");
    const variantRows = document.getElementById("variant-rows");

    function setSelectOptions(select, options, selectedValue) {
        select.replaceChildren();
        options.forEach(function (option) {
            select.add(new Option(
                option.label,
                option.value,
                false,
                option.value === selectedValue
            ));
        });
    }

    function makeRemoveButton(label) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "text-button remove-row";
        button.setAttribute("aria-label", label);
        button.textContent = "Remove";
        return button;
    }

    function tagsForCategory() {
        return tagsByCategory[categorySelect.value] || [];
    }

    function configureCharacteristicRow(row, selectedValueId) {
        const tagSelect = row.querySelector(".characteristic-tag");
        const valueSelect = row.querySelector(".characteristic-value");
        const newTag = row.querySelector(".characteristic-new-tag");
        const newValue = row.querySelector(".characteristic-new-value");
        const tags = tagsForCategory();
        const selectedTag = tagSelect.value;
        const tagOptions = [{ label: "Choose a tag", value: "" }]
            .concat(tags.map(function (tag) {
                return { label: tag.name, value: String(tag.id) };
            }))
            .concat([{ label: "Add a new tag", value: "__new__" }]);

        function refreshValues(selectedId) {
            const tag = tags.find(function (item) {
                return String(item.id) === tagSelect.value;
            });
            const options = [{ label: "Choose a value", value: "" }]
                .concat((tag ? tag.values : []).map(function (item) {
                    return { label: item.value, value: String(item.id) };
                }))
                .concat([{ label: "Add a new value", value: "__new__" }]);
            setSelectOptions(valueSelect, options, selectedId || "");
            if (
                selectedId === "__new__"
                || tagSelect.value === "__new__"
                || (tag && tag.values.length === 0)
            ) {
                valueSelect.value = "__new__";
            }
            newValue.hidden = valueSelect.value !== "__new__";
        }

        setSelectOptions(tagSelect, tagOptions, selectedTag);
        newTag.hidden = tagSelect.value !== "__new__";
        refreshValues(selectedValueId || valueSelect.value);
        tagSelect.onchange = function () {
            newTag.hidden = tagSelect.value !== "__new__";
            newTag.value = "";
            newValue.value = "";
            refreshValues("");
        };
        valueSelect.onchange = function () {
            newValue.hidden = valueSelect.value !== "__new__";
            newValue.value = "";
        };
    }

    function makeCharacteristicRow() {
        const row = document.createElement("div");
        row.className = "repeatable-row characteristic-row";
        const tagSelect = document.createElement("select");
        tagSelect.name = "characteristic_tag_id";
        tagSelect.className = "characteristic-tag";
        tagSelect.setAttribute("aria-label", "Characteristic tag");
        const newTag = document.createElement("input");
        newTag.name = "characteristic_new_tag";
        newTag.className = "characteristic-new-tag";
        newTag.maxLength = 80;
        newTag.placeholder = "New tag";
        newTag.setAttribute("aria-label", "New characteristic tag");
        const valueSelect = document.createElement("select");
        valueSelect.name = "characteristic_value_id";
        valueSelect.className = "characteristic-value";
        valueSelect.setAttribute("aria-label", "Characteristic value");
        const newValue = document.createElement("input");
        newValue.name = "characteristic_new_value";
        newValue.className = "characteristic-new-value";
        newValue.maxLength = 255;
        newValue.placeholder = "New value";
        newValue.setAttribute("aria-label", "New characteristic value");
        row.append(
            tagSelect,
            newTag,
            valueSelect,
            newValue,
            makeRemoveButton("Remove characteristic")
        );
        configureCharacteristicRow(row, "");
        characteristicRows.append(row);
    }

    function variantTypesForCategory() {
        return variantTypesByCategory[categorySelect.value] || [];
    }

    function field(labelText, inputName, type, placeholder, value) {
        const label = document.createElement("label");
        label.className = "variant-field";
        label.append(document.createTextNode(labelText));
        const input = document.createElement("input");
        input.name = inputName;
        input.type = type;
        input.placeholder = placeholder;
        input.value = value || "";
        input.setAttribute("aria-label", labelText);
        label.append(input);
        return { label: label, input: input };
    }

    function configureVariantRow(row) {
        const typeSelect = row.querySelector(".variant-type");
        const typeInput = row.querySelector(".variant-new-type");
        const valueInput = row.querySelector(".variant-value");
        const unitField = row.querySelector(".variant-unit-field");
        const unitSelect = row.querySelector(".variant-unit");
        const unitInput = row.querySelector(".variant-new-unit");
        const types = variantTypesForCategory();
        const selectedType = typeSelect.value;
        const typeOptions = [{ label: "Choose a type", value: "" }]
            .concat(types.map(function (type) {
                return { label: type.name, value: type.name };
            }));
        if (selectedType && !types.some(function (type) {
            return type.name === selectedType;
        })) {
            typeOptions.push({ label: selectedType, value: selectedType });
        }
        typeOptions.push({ label: "Add a new type", value: "__new__" });
        setSelectOptions(typeSelect, typeOptions, selectedType);

        function refreshUnits(selectedUnit) {
            const effectiveType = typeSelect.value === "__new__"
                ? typeInput.value
                : typeSelect.value;
            const isWeight = effectiveType.trim().toLowerCase() === "weight";
            unitField.hidden = !isWeight;
            typeInput.hidden = typeSelect.value !== "__new__";
            if (!isWeight) {
                unitSelect.value = "";
                unitInput.value = "";
                unitInput.hidden = true;
                valueInput.type = "text";
                valueInput.removeAttribute("min");
                valueInput.removeAttribute("step");
                return;
            }
            const type = types.find(function (item) {
                return item.name.toLowerCase() === effectiveType.trim().toLowerCase();
            });
            const units = type ? type.units.slice() : [];
            if (selectedUnit && selectedUnit !== "__new__" && !units.includes(selectedUnit)) {
                units.push(selectedUnit);
            }
            const unitOptions = [{ label: "No unit", value: "" }]
                .concat(units.map(function (unit) {
                    return { label: unit, value: unit };
                }))
                .concat([{ label: "Add a new unit", value: "__new__" }]);
            setSelectOptions(unitSelect, unitOptions, selectedUnit || "");
            unitInput.hidden = unitSelect.value !== "__new__";
            valueInput.type = "number";
            valueInput.min = "0.01";
            valueInput.step = "any";
        }

        refreshUnits(unitSelect.value);
        typeSelect.onchange = function () {
            typeInput.hidden = typeSelect.value !== "__new__";
            typeInput.value = "";
            unitInput.value = "";
            refreshUnits("");
        };
        unitSelect.onchange = function () {
            unitInput.hidden = unitSelect.value !== "__new__";
            unitInput.value = "";
            refreshUnits(unitSelect.value);
        };
        typeInput.oninput = function () {
            unitInput.value = "";
            refreshUnits("");
        };
    }

    function makeVariantRow() {
        const row = document.createElement("div");
        row.className = "repeatable-row variant-row";
        const id = document.createElement("input");
        id.type = "hidden";
        id.name = "variant_id";

        const typeField = document.createElement("label");
        typeField.className = "variant-field";
        typeField.append(document.createTextNode("Type"));
        const typeSelect = document.createElement("select");
        typeSelect.name = "variant_name";
        typeSelect.className = "variant-type";
        typeSelect.setAttribute("aria-label", "Variant type");
        const typeInput = document.createElement("input");
        typeInput.name = "variant_new_type";
        typeInput.className = "variant-new-type";
        typeInput.maxLength = 80;
        typeInput.placeholder = "New type";
        typeInput.setAttribute("aria-label", "New variant type");
        typeInput.hidden = true;
        typeField.append(typeSelect, typeInput);

        const valueField = field("Value", "variant_value", "text", "Enter a value");
        valueField.input.className = "variant-value";
        const unitField = document.createElement("label");
        unitField.className = "variant-field variant-unit-field";
        unitField.hidden = true;
        unitField.append(document.createTextNode("Unit"));
        const unitSelect = document.createElement("select");
        unitSelect.name = "variant_unit";
        unitSelect.className = "variant-unit";
        unitSelect.setAttribute("aria-label", "Variant unit");
        const unitInput = document.createElement("input");
        unitInput.name = "variant_new_unit";
        unitInput.className = "variant-new-unit";
        unitInput.maxLength = 20;
        unitInput.placeholder = "New unit";
        unitInput.setAttribute("aria-label", "New variant unit");
        unitInput.hidden = true;
        unitField.append(unitSelect, unitInput);

        const priceField = field(
            "Price override", "variant_price", "number", "Use product price"
        );
        priceField.input.min = "1";
        priceField.input.step = "1";
        const stockField = field("Stock quantity", "variant_stock", "number", "0");
        stockField.input.min = "0";
        const activeField = document.createElement("label");
        activeField.className = "check-field variant-active-field";
        const activeInput = document.createElement("input");
        activeInput.type = "checkbox";
        activeInput.name = "variant_active_new";
        activeInput.checked = true;
        activeField.append(activeInput, document.createTextNode("Active"));

        row.append(
            id,
            typeField,
            valueField.label,
            unitField,
            priceField.label,
            stockField.label,
            activeField,
            makeRemoveButton("Remove product option")
        );
        configureVariantRow(row);
        variantRows.append(row);
    }

    document.querySelectorAll(".characteristic-row").forEach(function (row) {
        configureCharacteristicRow(
            row, row.querySelector(".characteristic-value").value
        );
    });
    document.querySelectorAll(".variant-row").forEach(configureVariantRow);
    document.getElementById("add-characteristic").addEventListener(
        "click", makeCharacteristicRow
    );
    document.getElementById("add-variant").addEventListener("click", makeVariantRow);
    categorySelect.addEventListener("change", function () {
        characteristicRows.replaceChildren();
        variantRows.replaceChildren();
    });
    document.addEventListener("click", function (event) {
        if (event.target.matches(".remove-row")) {
            event.target.closest(".repeatable-row").remove();
        }
    });

    const discountType = document.getElementById("discount-type");
    const discountValue = document.getElementById("discount-value");
    const priceInput = document.getElementById("product-price");
    const preview = document.getElementById("discount-preview");
    function updateDiscountPreview() {
        const type = discountType.value;
        discountValue.disabled = type === "none";
        discountValue.step = "1";
        discountValue.max = type === "percent" ? "99" : "";
        if (type === "none") {
            preview.textContent = "No discount applied";
            return;
        }
        const price = Number(priceInput.value);
        const discount = Number(discountValue.value);
        if (!price || !discount) {
            preview.textContent = "";
            return;
        }
        const salePrice = type === "percent"
            ? price * (1 - discount / 100)
            : price - discount;
        preview.textContent = salePrice > 0
            ? "Sale price: ₹" + salePrice.toFixed(2)
            : "Discount must be lower than the product price";
    }
    [discountType, discountValue, priceInput].forEach(function (input) {
        input.addEventListener("input", updateDiscountPreview);
        input.addEventListener("change", updateDiscountPreview);
    });
    updateDiscountPreview();
});
