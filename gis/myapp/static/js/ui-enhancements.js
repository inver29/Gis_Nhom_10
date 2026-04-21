(function () {
    function initDjangoValidationForms(scope) {
        (scope || document).querySelectorAll("form").forEach(function (form) {
            if (!form.hasAttribute("novalidate")) {
                form.setAttribute("novalidate", "novalidate");
            }
        });
    }

    function initPasswordToggles(scope) {
        (scope || document).querySelectorAll('input[data-password-toggle="1"]').forEach(function (input) {
            if (input.dataset.passwordToggleReady === "1") {
                return;
            }
            input.dataset.passwordToggleReady = "1";

            var wrapper = document.createElement("div");
            wrapper.className = "password-toggle-field";
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);

            var button = document.createElement("button");
            button.type = "button";
            button.className = "password-toggle-button";
            button.setAttribute("aria-label", "Hiện hoặc ẩn mật khẩu");
            button.innerHTML = '<i class="fas fa-eye"></i>';

            button.addEventListener("click", function () {
                var nextType = input.type === "password" ? "text" : "password";
                input.type = nextType;
                button.innerHTML = nextType === "password"
                    ? '<i class="fas fa-eye"></i>'
                    : '<i class="fas fa-eye-slash"></i>';
            });

            wrapper.appendChild(button);
        });
    }

    function initSearchableSelects(scope) {
        if (typeof window.Choices === "undefined") {
            return;
        }

        (scope || document).querySelectorAll("select").forEach(function (select) {
            if (select.dataset.choicesReady === "1") {
                return;
            }
            if (select.disabled || select.closest(".choices")) {
                return;
            }

            var optionCount = select.options ? select.options.length : 0;
            var isSearchable = select.dataset.searchableSelect === "1" || optionCount >= 8;
            if (!isSearchable) {
                return;
            }

            select.dataset.choicesReady = "1";
            new window.Choices(select, {
                allowHTML: false,
                shouldSort: false,
                searchEnabled: true,
                itemSelectText: "",
                searchPlaceholderValue: "Gõ để tìm...",
                noResultsText: "Không có kết quả phù hợp",
                noChoicesText: "Không còn lựa chọn",
                loadingText: "Đang tải...",
                removeItemButton: false,
            });
        });
    }

    function initRangeOutputs(scope) {
        (scope || document).querySelectorAll('input[type="range"][data-range-output]').forEach(function (input) {
            if (input.dataset.rangeOutputReady === "1") {
                return;
            }
            input.dataset.rangeOutputReady = "1";

            var output = document.createElement("div");
            output.className = "ui-range-output";
            output.setAttribute("data-range-output-display", input.getAttribute("data-range-output") || "");
            input.insertAdjacentElement("afterend", output);

            function syncOutput() {
                output.textContent = "Mức hiện tại: " + String(input.value || "0") + "%";
            }

            input.addEventListener("input", syncOutput);
            input.addEventListener("change", syncOutput);
            syncOutput();
        });
    }

    function boot(scope) {
        initDjangoValidationForms(scope);
        initPasswordToggles(scope);
        initSearchableSelects(scope);
        initRangeOutputs(scope);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            boot(document);
        });
    } else {
        boot(document);
    }

    if (document.body && window.MutationObserver) {
        new MutationObserver(function (mutations) {
            mutations.forEach(function (mutation) {
                mutation.addedNodes.forEach(function (node) {
                    if (!node || node.nodeType !== 1) {
                        return;
                    }
                    boot(node);
                });
            });
        }).observe(document.body, { childList: true, subtree: true });
    }

    window.uiEnhancements = {
        boot: boot,
    };
})();
