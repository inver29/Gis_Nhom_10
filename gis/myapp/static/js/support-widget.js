(function () {
    function initSupportWidgets() {
        var widgets = document.querySelectorAll('[data-support-widget]');
        widgets.forEach(function (widget) {
            if (widget.dataset.supportReady === '1') {
                return;
            }

            var openButton = widget.querySelector('[data-support-open]');
            var closeButton = widget.querySelector('[data-support-close]');
            var panel = widget.querySelector('.support-widget__panel');
            var backdrop = widget.querySelector('[data-support-backdrop]');
            var lastFocused = null;

            if (!openButton || !panel || !backdrop) {
                return;
            }

            function setOpen(isOpen) {
                widget.classList.toggle('is-open', isOpen);
                openButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
                panel.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
                if (isOpen) {
                    backdrop.hidden = false;
                    lastFocused = document.activeElement;
                    document.body.classList.add('support-widget-open');
                    window.setTimeout(function () {
                        if (closeButton) {
                            closeButton.focus();
                        }
                    }, 30);
                } else {
                    backdrop.hidden = true;
                    document.body.classList.remove('support-widget-open');
                    if (lastFocused && typeof lastFocused.focus === 'function') {
                        lastFocused.focus();
                    }
                }
            }

            openButton.addEventListener('click', function () {
                setOpen(!widget.classList.contains('is-open'));
            });

            if (closeButton) {
                closeButton.addEventListener('click', function () {
                    setOpen(false);
                });
            }

            backdrop.addEventListener('click', function () {
                setOpen(false);
            });

            widget.addEventListener('keydown', function (event) {
                if (event.key === 'Escape' && widget.classList.contains('is-open')) {
                    setOpen(false);
                }
            });

            widget.dataset.supportReady = '1';
        });
    }

    document.addEventListener('DOMContentLoaded', initSupportWidgets);
})();
