/*
 * Vietnam Islands Overlay for Leaflet
 *
 * Overlays Vietnamese-language labels for Hoàng Sa & Trường Sa archipelagos
 * on top of any Leaflet base layer. Overlay-only — does not modify the
 * underlying tile provider, so it works the same regardless of which tile
 * source is used.
 *
 * Usage:
 *   attachLeafletBaseLayer(map);
 *   attachVietnamIslandsOverlay(map);
 */
(function () {
    "use strict";

    if (typeof window === "undefined") {
        return;
    }

    var ARCHIPELAGOS = [
        {
            key: "hoangSa",
            name: "Quần đảo Hoàng Sa",
            subtitle: "Huyện Hoàng Sa, TP. Đà Nẵng – Việt Nam",
            bounds: [[15.6, 111.0], [17.2, 113.0]],
            center: [16.45, 112.0],
            islands: [
                { name: "Đảo Phú Lâm", coords: [16.835, 112.342] },
                { name: "Đảo Hoàng Sa", coords: [16.533, 111.617] },
                { name: "Đảo Quang Ảnh", coords: [16.450, 111.604] },
                { name: "Đảo Tri Tôn", coords: [15.780, 111.200] },
                { name: "Đảo Lin Côn", coords: [16.667, 112.733] },
                { name: "Đảo Quang Hoà", coords: [16.450, 111.700] }
            ]
        },
        {
            key: "truongSa",
            name: "Quần đảo Trường Sa",
            subtitle: "Huyện Trường Sa, tỉnh Khánh Hoà – Việt Nam",
            bounds: [[6.5, 109.5], [12.0, 117.5]],
            center: [9.5, 113.5],
            islands: [
                { name: "Đảo Trường Sa", coords: [8.650, 111.917] },
                { name: "Đảo Song Tử Tây", coords: [11.433, 114.333] },
                { name: "Đảo Sinh Tồn", coords: [9.883, 114.333] },
                { name: "Đảo Nam Yết", coords: [10.183, 114.367] },
                { name: "Đảo Sơn Ca", coords: [10.217, 114.483] },
                { name: "Đảo Phan Vinh", coords: [8.967, 113.683] },
                { name: "Đảo An Bang", coords: [7.883, 112.917] },
                { name: "Đảo Thuyền Chài", coords: [7.850, 113.300] },
                { name: "Đảo Đá Lát", coords: [8.667, 111.667] }
            ]
        }
    ];

    window.VIETNAM_ISLANDS_OVERLAY_DATA = ARCHIPELAGOS;

    function buildArchipelagoLayers(config) {
        var L = window.L;
        var layers = { rect: null, label: null, islands: [] };

        layers.rect = L.rectangle(config.bounds, {
            color: "#DA251D",
            weight: 1.6,
            opacity: 0.85,
            fillColor: "#FFCD00",
            fillOpacity: 0.04,
            dashArray: "6 4",
            interactive: false,
            bubblingMouseEvents: false
        });

        layers.label = L.marker(config.center, {
            icon: L.divIcon({
                className: "vn-island-label",
                html:
                    '<div class="vn-island-label__title">' + config.name + '</div>' +
                    '<div class="vn-island-label__subtitle">' + config.subtitle + '</div>',
                iconSize: null,
                iconAnchor: [0, 0]
            }),
            interactive: false,
            keyboard: false
        });

        config.islands.forEach(function (island) {
            var marker = L.marker(island.coords, {
                icon: L.divIcon({
                    className: "vn-island-marker",
                    html:
                        '<span class="vn-island-marker__dot" aria-hidden="true"></span>' +
                        '<span class="vn-island-marker__name">' + island.name + '</span>',
                    iconSize: null,
                    iconAnchor: [4, 4]
                }),
                interactive: false,
                keyboard: false
            });
            layers.islands.push(marker);
        });

        return layers;
    }

    window.attachVietnamIslandsOverlay = function (leafletMap, options) {
        if (!leafletMap || !window.L) {
            return null;
        }
        options = options || {};
        var detailZoom = typeof options.detailZoom === "number" ? options.detailZoom : 7;
        var labelZoom = typeof options.labelZoom === "number" ? options.labelZoom : 4;

        var overlay = window.L.layerGroup();
        var detailMarkers = [];
        var labelMarkers = [];

        ARCHIPELAGOS.forEach(function (archipelago) {
            var layers = buildArchipelagoLayers(archipelago);
            overlay.addLayer(layers.rect);
            overlay.addLayer(layers.label);
            labelMarkers.push(layers.label);
            layers.islands.forEach(function (marker) {
                overlay.addLayer(marker);
                detailMarkers.push(marker);
            });
        });

        overlay.addTo(leafletMap);

        function setDisplay(marker, visible) {
            var element = marker.getElement && marker.getElement();
            if (!element) {
                return;
            }
            element.style.display = visible ? "" : "none";
        }

        function syncVisibility() {
            var zoom = leafletMap.getZoom();
            var showDetail = zoom >= detailZoom;
            var showLabels = zoom >= labelZoom;
            detailMarkers.forEach(function (marker) {
                setDisplay(marker, showDetail);
            });
            labelMarkers.forEach(function (marker) {
                setDisplay(marker, showLabels);
            });
        }

        leafletMap.on("zoomend", syncVisibility);
        // Initial pass once the markers are rendered.
        if (typeof window.requestAnimationFrame === "function") {
            window.requestAnimationFrame(syncVisibility);
        } else {
            window.setTimeout(syncVisibility, 0);
        }

        return overlay;
    };
})();
