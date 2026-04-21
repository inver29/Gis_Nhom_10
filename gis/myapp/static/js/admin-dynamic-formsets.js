(function () {
    'use strict';

    function updateDeleteState(card) {
        if (!card) return;
        var deleteInput = card.querySelector('input[name$="-DELETE"]');
        card.classList.toggle('is-marked-delete', !!(deleteInput && deleteInput.checked));
    }

    function findCustomWrapper(input) {
        if (!input) return null;
        return input.closest('[data-quick-wrapper]') || input.parentElement;
    }

    function syncQuickChoice(select) {
        if (!select) return;
        var targetName = select.getAttribute('data-quick-choice');
        if (!targetName) return;
        var scope = select.closest('[data-formset-card]') || select.closest('form') || document;
        scope.querySelectorAll('[data-quick-custom-input="' + targetName + '"]').forEach(function (input) {
            var wrapper = findCustomWrapper(input);
            var showCustomInput = select.value === '__custom__';
            if (wrapper) {
                wrapper.classList.toggle('is-hidden', !showCustomInput);
            }
        });
    }

    function initQuickChoices(scope) {
        (scope || document).querySelectorAll('select[data-quick-choice]').forEach(function (select) {
            if (select.dataset.quickChoiceReady !== '1') {
                select.dataset.quickChoiceReady = '1';
                select.addEventListener('change', function () {
                    syncQuickChoice(select);
                });
            }
            syncQuickChoice(select);
        });
    }

    function updateSectionCount(section) {
        if (!section) return;
        var cards = Array.prototype.slice.call(section.querySelectorAll('[data-formset-card]'));
        var count = cards.filter(function (card) {
            var deleteInput = card.querySelector('input[name$="-DELETE"]');
            return !(deleteInput && deleteInput.checked);
        }).length;
        var countNode = section.querySelector('[data-formset-count]');
        if (!countNode) return;
        var singular = section.getAttribute('data-item-label-singular') || 'mục';
        var plural = section.getAttribute('data-item-label-plural') || singular;
        countNode.textContent = count + ' ' + (count === 1 ? singular : plural);
    }

    function initFormsetCard(section, card) {
        if (!card || card.dataset.formsetCardReady === '1') return;
        card.dataset.formsetCardReady = '1';
        card.querySelectorAll('input[name$="-DELETE"]').forEach(function (deleteInput) {
            deleteInput.addEventListener('change', function () {
                updateDeleteState(card);
                updateSectionCount(section);
            });
        });
        updateDeleteState(card);
        initQuickChoices(card);
        if (window.uiEnhancements && typeof window.uiEnhancements.boot === 'function') {
            window.uiEnhancements.boot(card);
        }
        if (typeof window.ensureAdminRichEditors === 'function') {
            window.ensureAdminRichEditors();
        }
    }

    function initDynamicFormset(section) {
        if (!section || section.dataset.dynamicFormsetReady === '1') return;
        section.dataset.dynamicFormsetReady = '1';

        var prefix = section.getAttribute('data-prefix');
        var list = section.querySelector('[data-formset-list]');
        var template = section.querySelector('template[data-formset-template]');
        var addButton = section.querySelector('[data-formset-add]');
        var totalFormsInput = prefix ? document.getElementById('id_' + prefix + '-TOTAL_FORMS') : null;

        if (!list || !template || !addButton || !totalFormsInput) {
            initQuickChoices(section);
            return;
        }

        list.querySelectorAll('[data-formset-card]').forEach(function (card) {
            initFormsetCard(section, card);
        });
        updateSectionCount(section);

        addButton.addEventListener('click', function () {
            var currentIndex = parseInt(totalFormsInput.value || '0', 10);
            if (Number.isNaN(currentIndex)) {
                currentIndex = list.querySelectorAll('[data-formset-card]').length;
            }

            var html = template.innerHTML.replace(/__prefix__/g, String(currentIndex));
            var wrapper = document.createElement('div');
            wrapper.innerHTML = html.trim();
            var card = wrapper.firstElementChild;
            if (!card) return;

            list.appendChild(card);
            totalFormsInput.value = String(currentIndex + 1);
            initFormsetCard(section, card);
            updateSectionCount(section);
        });
    }

    function boot(scope) {
        (scope || document).querySelectorAll('[data-dynamic-formset]').forEach(function (section) {
            initDynamicFormset(section);
        });
        initQuickChoices(scope || document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            boot(document);
        });
    } else {
        boot(document);
    }

    window.adminDynamicFormsets = {
        boot: boot,
    };
})();
