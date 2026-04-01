(function () {
    if (document.documentElement) {
        document.documentElement.classList.add("has-motion");
    }

    function initSplideCarousels() {
        if (typeof window.Splide === "undefined") {
            return;
        }

        function readBooleanAttribute(element, name, fallback) {
            var value = element.getAttribute(name);
            if (value === null || value === "") {
                return fallback;
            }
            return value === "true" || value === "1";
        }

        var carousels = document.querySelectorAll("[data-site-splide]");
        carousels.forEach(function (element) {
            if (element.dataset.splideMounted === "1") {
                return;
            }

            var perPage = parseInt(element.getAttribute("data-per-page") || "4", 10);
            var gap = element.getAttribute("data-gap") || "18px";
            var requestedType = element.getAttribute("data-type") || "";
            var autoplay = readBooleanAttribute(element, "data-autoplay", false);
            var pagination = readBooleanAttribute(element, "data-pagination", false);
            var arrows = readBooleanAttribute(element, "data-arrows", true);
            var interval = parseInt(element.getAttribute("data-interval") || "5000", 10);
            var slideCount = element.querySelectorAll(".splide__slide").length;
            var shouldLoop = slideCount > perPage;
            var resolvedType = requestedType || (shouldLoop ? "loop" : "slide");
            var resolvedArrows = arrows && slideCount > 1;
            var resolvedPagination = pagination && slideCount > 1;
            var resolvedInterval = Number.isNaN(interval) ? 5000 : interval;

            new window.Splide(element, {
                type: resolvedType,
                rewind: resolvedType !== "loop",
                pagination: resolvedPagination,
                arrows: resolvedArrows,
                drag: slideCount > 1,
                gap: gap,
                perPage: perPage,
                perMove: 1,
                autoplay: autoplay && slideCount > 1,
                interval: resolvedInterval,
                pauseOnHover: true,
                pauseOnFocus: true,
                waitForTransition: false,
                breakpoints: {
                    1199: { perPage: Math.min(3, perPage) },
                    991: { perPage: Math.min(2, perPage) },
                    640: { perPage: 1 }
                }
            }).mount();

            element.dataset.splideMounted = "1";
        });
    }

    function initGallerySplides() {
        if (typeof window.Splide === "undefined") {
            return;
        }

        var galleries = document.querySelectorAll("[data-site-gallery]");
        galleries.forEach(function (gallery) {
            if (gallery.dataset.galleryMounted === "1") {
                return;
            }

            var mainElement = gallery.querySelector(".site-gallery-main");
            if (!mainElement) {
                return;
            }

            var thumbElement = gallery.querySelector(".site-gallery-thumbs");
            var slideCount = mainElement.querySelectorAll(".splide__slide").length;
            var hasMultipleSlides = slideCount > 1;
            var mainSplide = new window.Splide(mainElement, {
                type: hasMultipleSlides ? "loop" : "slide",
                rewind: !hasMultipleSlides,
                pagination: false,
                arrows: hasMultipleSlides,
                drag: hasMultipleSlides,
                speed: 520,
                keyboard: "global",
                easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                flickPower: 140,
                waitForTransition: false
            });

            if (thumbElement) {
                var thumbSplide = new window.Splide(thumbElement, {
                    rewind: !hasMultipleSlides,
                    gap: "14px",
                    pagination: false,
                    arrows: false,
                    fixedWidth: 104,
                    fixedHeight: 104,
                    drag: hasMultipleSlides,
                    isNavigation: true,
                    focus: "center",
                    trimSpace: false,
                    breakpoints: {
                        991: {
                            fixedWidth: 88,
                            fixedHeight: 88,
                            gap: "12px"
                        },
                        640: {
                            fixedWidth: 72,
                            fixedHeight: 72,
                            gap: "10px"
                        }
                    }
                });

                mainSplide.sync(thumbSplide);
                thumbSplide.mount();
            }

            mainSplide.mount();
            gallery.siteGalleryInstances = {
                mainSplide: mainSplide,
                thumbSplide: thumbElement ? thumbSplide : null
            };
            gallery.dataset.galleryMounted = "1";
        });
    }

    function initProductZoomGalleries() {
        var galleries = document.querySelectorAll("[data-product-gallery]");

        galleries.forEach(function (gallery) {
            if (gallery.dataset.productZoomReady === "1") {
                return;
            }

            var mainElement = gallery.querySelector(".site-gallery-main");
            var modalSelector = gallery.getAttribute("data-modal-target");
            var modal = modalSelector ? document.querySelector(modalSelector) : null;
            var modalGallery = modal ? modal.querySelector("[data-site-gallery]") : null;

            if (!mainElement) {
                return;
            }

            function getMainInstance() {
                return gallery.siteGalleryInstances ? gallery.siteGalleryInstances.mainSplide : null;
            }

            function openModalAt(index) {
                if (!modal) {
                    return;
                }

                modal.classList.add("is-open");
                modal.setAttribute("aria-hidden", "false");
                document.body.classList.add("site-modal-open");

                if (window.siteUtils && typeof window.siteUtils.initGallerySplides === "function") {
                    window.siteUtils.initGallerySplides();
                }

                window.setTimeout(function () {
                    if (!modalGallery || !modalGallery.siteGalleryInstances || !modalGallery.siteGalleryInstances.mainSplide) {
                        return;
                    }
                    modalGallery.siteGalleryInstances.mainSplide.refresh();
                    modalGallery.siteGalleryInstances.mainSplide.go(index || 0);
                    if (modalGallery.siteGalleryInstances.thumbSplide) {
                        modalGallery.siteGalleryInstances.thumbSplide.refresh();
                    }
                }, 40);
            }

            function closeModal() {
                if (!modal) {
                    return;
                }
                modal.classList.remove("is-open");
                modal.setAttribute("aria-hidden", "true");
                document.body.classList.remove("site-modal-open");
            }

            gallery.querySelectorAll("[data-gallery-open]").forEach(function (button) {
                button.addEventListener("click", function () {
                    var mainInstance = getMainInstance();
                    var activeIndex = mainInstance ? mainInstance.index : 0;
                    openModalAt(activeIndex);
                });
            });

            if (modal) {
                modal.addEventListener("click", function (event) {
                    if (event.target === modal || event.target.hasAttribute("data-gallery-close") || event.target.closest("[data-gallery-close]")) {
                        closeModal();
                    }
                });
            }

            gallery.dataset.productZoomReady = "1";
        });

        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") {
                return;
            }
            document.querySelectorAll(".product-gallery-modal.is-open").forEach(function (modal) {
                modal.classList.remove("is-open");
                modal.setAttribute("aria-hidden", "true");
            });
            document.body.classList.remove("site-modal-open");
        });
    }

    function initRevealAnimations() {
        var items = document.querySelectorAll("[data-reveal]");
        if (!items.length) {
            return;
        }

        if (!("IntersectionObserver" in window)) {
            items.forEach(function (item) {
                item.classList.add("is-visible");
            });
            return;
        }

        var observer = new window.IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) {
                    return;
                }

                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            });
        }, {
            threshold: 0.16,
            rootMargin: "0px 0px -8% 0px"
        });

        items.forEach(function (item, index) {
            item.style.transitionDelay = String((index % 6) * 70) + "ms";
            observer.observe(item);
        });
    }

    function animateCountUp(element, targetValue) {
        var start = null;
        var duration = 1100;
        var formatter = new Intl.NumberFormat("vi-VN");

        function step(timestamp) {
            if (start === null) {
                start = timestamp;
            }

            var progress = Math.min((timestamp - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            var value = Math.round(targetValue * eased);
            element.textContent = formatter.format(value);

            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        }

        window.requestAnimationFrame(step);
    }

    function initCountUps() {
        var counters = document.querySelectorAll("[data-countup]");
        if (!counters.length) {
            return;
        }

        if (!("IntersectionObserver" in window)) {
            counters.forEach(function (counter) {
                var fallbackValue = parseInt(counter.getAttribute("data-countup"), 10);
                if (!Number.isNaN(fallbackValue)) {
                    counter.textContent = new Intl.NumberFormat("vi-VN").format(fallbackValue);
                }
            });
            return;
        }

        var observer = new window.IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting || entry.target.dataset.counted === "1") {
                    return;
                }

                var targetValue = parseInt(entry.target.getAttribute("data-countup"), 10);
                if (!Number.isNaN(targetValue)) {
                    entry.target.dataset.counted = "1";
                    animateCountUp(entry.target, targetValue);
                }

                observer.unobserve(entry.target);
            });
        }, {
            threshold: 0.35
        });

        counters.forEach(function (counter) {
            observer.observe(counter);
        });
    }

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            var cookies = document.cookie.split(";");
            for (var i = 0; i < cookies.length; i += 1) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function ensureToastStack() {
        var stack = document.querySelector("[data-site-toast-stack]");
        if (stack) {
            return stack;
        }

        stack = document.createElement("div");
        stack.className = "site-toast-stack";
        stack.setAttribute("data-site-toast-stack", "1");
        document.body.appendChild(stack);
        return stack;
    }

    function showToast(message, tone) {
        var stack = ensureToastStack();
        var toast = document.createElement("div");
        toast.className = "site-toast site-toast--" + (tone || "info");
        toast.innerHTML = [
            "<i class=\"fas " + (tone === "error" ? "fa-exclamation-circle" : "fa-check-circle") + " mt-1\"></i>",
            "<div class=\"flex-grow-1\">" + message + "</div>",
            "<button type=\"button\" aria-label=\"Đóng\"><i class=\"fas fa-times\"></i></button>"
        ].join("");

        var closeButton = toast.querySelector("button");
        closeButton.addEventListener("click", function () {
            toast.remove();
        });

        stack.appendChild(toast);
        window.setTimeout(function () {
            toast.remove();
        }, 3200);
    }

    function updateCartCount(nextCount) {
        var targets = document.querySelectorAll("[data-cart-count]");
        targets.forEach(function (target) {
            target.textContent = nextCount;
        });
    }

    function submitAddToCartForm(form) {
        if (form.classList.contains("is-loading")) {
            return;
        }

        form.classList.add("is-loading");

        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: {
                "X-CSRFToken": getCookie("csrftoken"),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json"
            }
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return {
                        ok: response.ok,
                        data: data
                    };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    throw new Error(payload.data && payload.data.message ? payload.data.message : "Không thể thêm vào giỏ hàng.");
                }

                if (payload.data && typeof payload.data.cart_items_count !== "undefined") {
                    updateCartCount(payload.data.cart_items_count);
                }

                showToast(payload.data && payload.data.message ? payload.data.message : "Đã thêm vào giỏ hàng.", "success");
            })
            .catch(function (error) {
                showToast(error.message || "Không thể thêm vào giỏ hàng lúc này.", "error");
            })
            .finally(function () {
                form.classList.remove("is-loading");
            });
    }

    window.siteUtils = {
        getCookie: getCookie,
        showToast: showToast,
        updateCartCount: updateCartCount,
        initSplideCarousels: initSplideCarousels,
        initGallerySplides: initGallerySplides,
        initRevealAnimations: initRevealAnimations,
        initCountUps: initCountUps,
        initProductZoomGalleries: initProductZoomGalleries
    };

    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!form.matches(".js-add-to-cart-form")) {
            return;
        }

        event.preventDefault();
        submitAddToCartForm(form);
    });

    document.addEventListener("DOMContentLoaded", function () {
        initSplideCarousels();
        initGallerySplides();
        initRevealAnimations();
        initCountUps();
        initProductZoomGalleries();
    });
})();
