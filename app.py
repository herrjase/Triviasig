"use strict";

document.addEventListener("DOMContentLoaded", function () {
    const mapStatus = document.getElementById("map-status");
    const regionPanel = document.getElementById("region-panel");
    const regionName = document.getElementById("region-name");
    const regionIdElement = document.getElementById("region-id");
    const regionDescription = document.getElementById("region-description");
    const regionOwner = document.getElementById("region-owner");
    const regionArmy = document.getElementById("region-army");
    const regionPrice = document.getElementById("region-price");
    const closePanelButton = document.getElementById("close-panel");
    const regionsCount = document.getElementById("regions-count");

    let selectedLayer = null;
    let regionsLayer = null;

    const NEUTRAL_FILL = "#405b6b";
    const NEUTRAL_BORDER = "#a4b6c2";
    const SELECTED_BORDER = "#ffe58a";

    const map = L.map("world-map", {
        center: [25, 10],
        zoom: 2,
        minZoom: 2,
        maxZoom: 10,
        zoomControl: true,
        worldCopyJump: true,
        maxBounds: [[-85, -180], [85, 180]],
        maxBoundsViscosity: 0.7
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        subdomains: "abc",
        maxZoom: 19
    }).addTo(map);

    map.attributionControl.addAttribution(
        '<a href="https://gtamapdata.org/">GTAmap v1.1</a> — административные границы, CC BY 4.0'
    );

    // Принимаем только корректный HEX-цвет.
    function normalizeColor(value) {
        if (
            typeof value === "string" &&
            /^#[0-9a-fA-F]{6}$/.test(value)
        ) {
            return value;
        }

        return null;
    }

    // Определяем цвет региона по владельцу и его команде.
    function getRegionColor(feature) {
        const p = feature.properties || {};

        // Приоритет у цвета команды.
        if (p.team_id !== null && p.team_id !== undefined) {
            const teamColor = normalizeColor(p.team_color);

            if (teamColor) {
                return teamColor;
            }
        }

        // Если игрок не состоит в команде — личный цвет.
        if (p.owner_player_id !== null &&
            p.owner_player_id !== undefined) {
            const playerColor = normalizeColor(p.player_color);

            if (playerColor) {
                return playerColor;
            }
        }

        // Нейтральные регионы сохраняют прежний цвет.
        return NEUTRAL_FILL;
    }

    function getRegionStyle(feature) {
        return {
            color: NEUTRAL_BORDER,
            weight: 0.7,
            opacity: 0.9,
            fillColor: getRegionColor(feature),
            fillOpacity: 0.65
        };
    }

    function getSelectedStyle(feature) {
        return {
            color: SELECTED_BORDER,
            weight: 2.5,
            opacity: 1,
            fillColor: getRegionColor(feature),
            fillOpacity: 0.85
        };
    }

    function getRegionName(feature) {
        const p = feature.properties || {};

        return p.name ||
            p.NAME ||
            p.NAME_1 ||
            p.region ||
            p.admin1 ||
            p.shapeName ||
            "Неизвестный регион";
    }

    function getCountryName(feature) {
        const p = feature.properties || {};

        return p.admin ||
            p.country ||
            p.country_name ||
            p.ADMIN ||
            p.NAME_0 ||
            p.iso3 ||
            p.ISO3 ||
            "Страна не указана";
    }

    function selectRegion(layer, feature) {
        if (selectedLayer && regionsLayer) {
            regionsLayer.resetStyle(selectedLayer);
        }

        selectedLayer = layer;
        layer.setStyle(getSelectedStyle(feature));

        if (layer.bringToFront) {
            layer.bringToFront();
        }

        const p = feature.properties || {};

        regionName.textContent = getRegionName(feature);
        regionIdElement.textContent = p.region_id || "Нет ID";

        regionDescription.textContent =
            "Административный регион страны: " +
            getCountryName(feature) + ".";

        // Показываем имя игрока, а не название команды.
        regionOwner.textContent =
            p.owner || "Нейтральная территория";

        regionArmy.textContent =
            p.army !== undefined ? p.army : "Пока нет данных";

        regionPrice.textContent =
            p.price !== undefined && p.price > 0
                ? p.price
                : "Будет рассчитана";

        regionPanel.classList.add("visible");
    }

    function onEachRegion(feature, layer) {
        const name = getRegionName(feature);
        const country = getCountryName(feature);

        layer.on({
            mouseover: function () {
                if (layer !== selectedLayer) {
                    layer.setStyle({
                        color: "#e3edf4",
                        weight: 1.4,
                        fillColor: getRegionColor(feature),
                        fillOpacity: 0.85
                    });
                }
            },

            mouseout: function () {
                if (layer !== selectedLayer && regionsLayer) {
                    regionsLayer.resetStyle(layer);
                }
            },

            click: function () {
                selectRegion(layer, feature);
            }
        });

        layer.bindTooltip(name + " — " + country, {
            sticky: true,
            direction: "top",
            opacity: 0.95
        });
    }

    async function loadRegions() {
        mapStatus.textContent = "Загрузка регионов...";

        try {
            const response = await fetch("/api/regions");

            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }

            const geoData = await response.json();

            if (!Array.isArray(geoData.features) ||
                geoData.features.length === 0) {
                throw new Error(
                    geoData.details || "Регионы не найдены"
                );
            }

            regionsLayer = L.geoJSON(geoData, {
                style: getRegionStyle,
                onEachFeature: onEachRegion
            }).addTo(map);

            const count = geoData.features.length;

            regionsCount.textContent =
                count.toLocaleString("ru-RU");

            mapStatus.textContent =
                "Регионов: " + count.toLocaleString("ru-RU");

            map.setView([25, 10], 2);

        } catch (error) {
            console.error("Ошибка загрузки регионов:", error);

            mapStatus.textContent = "Ошибка загрузки регионов";
            regionsCount.textContent = "—";

            const errorBox = document.createElement("div");
            errorBox.className = "map-error";
            errorBox.textContent =
                "Не удалось загрузить регионы. Проверь запуск Flask и подключение к интернету.";

            document.getElementById("world-map")
                .appendChild(errorBox);
        }
    }

    closePanelButton.addEventListener("click", function () {
        regionPanel.classList.remove("visible");

        if (selectedLayer && regionsLayer) {
            regionsLayer.resetStyle(selectedLayer);
            selectedLayer = null;
        }

        regionIdElement.textContent = "—";
    });

    document.getElementById("login-button")
        .addEventListener("click", function () {
            alert(
                "Авторизация через Discord будет добавлена позднее."
            );
        });

    loadRegions();
});