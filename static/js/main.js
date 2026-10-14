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

    // Создание карты
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

    // Подложка OpenStreetMap
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        subdomains: "abc",
        maxZoom: 19
    }).addTo(map);

    map.attributionControl.addAttribution(
        '<a href="https://gtamapdata.org/">GTAmap v1.1</a> — административные границы, CC BY 4.0'
    );

    // Обычный стиль региона
    function getRegionStyle() {
        return {
            color: "#a4b6c2",
            weight: 0.7,
            opacity: 0.9,
            fillColor: "#405b6b",
            fillOpacity: 0.28
        };
    }

    // Стиль выбранного региона
    function getSelectedStyle() {
        return {
            color: "#ffe58a",
            weight: 2.5,
            opacity: 1,
            fillColor: "#d5b44a",
            fillOpacity: 0.65
        };
    }

    // Название региона
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

    // Название страны
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

    // Назначение ID регионам
    function assignRegionIds(features) {
        features.forEach(function (feature, index) {
            if (!feature.properties) {
                feature.properties = {};
            }

            feature.properties.region_id =
                "SIG-" + String(index + 1).padStart(4, "0");
        });
    }

    // Выбор региона
    function selectRegion(layer, feature) {
        if (selectedLayer && regionsLayer) {
            regionsLayer.resetStyle(selectedLayer);
        }

        selectedLayer = layer;
        layer.setStyle(getSelectedStyle());

        if (layer.bringToFront) {
            layer.bringToFront();
        }

        const name = getRegionName(feature);
        const country = getCountryName(feature);
        const regionId = feature.properties.region_id;

        regionName.textContent = name;
        regionIdElement.textContent = regionId;

        regionDescription.textContent =
            "Административный регион страны: " + country +
            ". Игровые характеристики и возможность захвата появятся позднее.";

        regionOwner.textContent = "Нейтральная территория";
        regionArmy.textContent = "Пока нет данных";
        regionPrice.textContent = "Будет рассчитана";

        regionPanel.classList.add("visible");
    }

    // Обработка регионов
    function onEachRegion(feature, layer) {
        const name = getRegionName(feature);
        const country = getCountryName(feature);

        layer.on({
            mouseover: function () {
                if (layer !== selectedLayer) {
                    layer.setStyle({
                        color: "#e3edf4",
                        weight: 1.4,
                        fillColor: "#6b8b9e",
                        fillOpacity: 0.5
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

    // Загрузка административных регионов
    async function loadRegions() {
        mapStatus.textContent = "Загрузка регионов...";

        const geoJsonUrl =
            "https://gtamapdata.org/data/web/global_adm1_2020.geojson";

        try {
            const response = await fetch(geoJsonUrl);

            if (!response.ok) {
                throw new Error("HTTP " + response.status);
            }

            const geoData = await response.json();

            if (
                !geoData ||
                !Array.isArray(geoData.features) ||
                geoData.features.length === 0
            ) {
                throw new Error("GeoJSON не содержит регионов.");
            }

            // Назначаем ID перед отображением регионов
            assignRegionIds(geoData.features);

            // Добавляем регионы на карту
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
            console.error("Ошибка загрузки карты SIgame:", error);

            mapStatus.textContent = "Ошибка загрузки регионов";
            regionsCount.textContent = "—";

            const errorBox = document.createElement("div");

            errorBox.className = "map-error";

            errorBox.innerHTML = `
                <strong>Не удалось загрузить границы регионов.</strong>
                <p>
                    Проверь подключение к интернету и обнови страницу.
                    Если ошибка повторяется, источник геоданных может быть
                    временно недоступен.
                </p>
            `;

            document.getElementById("world-map")
                .appendChild(errorBox);
        }
    }

    // Закрытие панели
    closePanelButton.addEventListener("click", function () {
        regionPanel.classList.remove("visible");

        if (selectedLayer && regionsLayer) {
            regionsLayer.resetStyle(selectedLayer);
            selectedLayer = null;
        }

        regionIdElement.textContent = "—";
    });

    // Кнопка входа через Discord
    document.getElementById("login-button")
        .addEventListener("click", function () {
            alert(
                "Авторизация через Discord будет добавлена " +
                "на следующем этапе разработки SIgame."
            );
        });

    // Запуск
    loadRegions();
});