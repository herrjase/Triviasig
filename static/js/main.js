"use strict";

/* ==========================================
   SIgame — ИНТЕРАКТИВНАЯ КАРТА МИРА
   ========================================== */

document.addEventListener("DOMContentLoaded", function () {

    const mapStatus = document.getElementById("map-status");

    const regionPanel = document.getElementById("region-panel");
    const regionName = document.getElementById("region-name");
    const regionDescription = document.getElementById("region-description");

    const regionOwner = document.getElementById("region-owner");
    const regionArmy = document.getElementById("region-army");
    const regionPrice = document.getElementById("region-price");

    const closePanelButton = document.getElementById("close-panel");
    const regionsCount = document.getElementById("regions-count");

    let selectedLayer = null;

    let countriesLayer = null;
    let countriesLoaded = 0;


    /* ==========================================
       1. СОЗДАНИЕ КАРТЫ
       ========================================== */

    const map = L.map("world-map", {

        center: [25, 10],

        zoom: 2,

        minZoom: 2,
        maxZoom: 10,

        zoomControl: true,

        worldCopyJump: true,

        maxBounds: [
            [-85, -180],
            [85, 180]
        ],

        maxBoundsViscosity: 0.7

    });


    /* ==========================================
       2. ГЕОГРАФИЧЕСКАЯ ПОДЛОЖКА
       ========================================== */

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',

            subdomains: "abc",

            maxZoom: 19
        }
    ).addTo(map);


    /* ==========================================
       3. СТИЛЬ ТЕРРИТОРИЙ
       ========================================== */

    function getCountryStyle() {

        return {

            color: "#a4b6c2",

            weight: 0.8,

            opacity: 0.9,

            fillColor: "#405b6b",

            fillOpacity: 0.28

        };

    }


    function getSelectedStyle() {

        return {

            color: "#ffe58a",

            weight: 2.5,

            opacity: 1,

            fillColor: "#d5b44a",

            fillOpacity: 0.65

        };

    }


    /* ==========================================
       4. НАЗВАНИЕ СТРАНЫ
       ========================================== */

    function getCountryName(feature) {

        const properties = feature.properties || {};

        return (
            properties.ADMIN ||
            properties.name ||
            properties.NAME ||
            properties.admin ||
            properties.NAME_EN ||
            "Неизвестная территория"
        );

    }


    /* ==========================================
       5. ВЫБОР СТРАНЫ
       ========================================== */

    function selectCountry(layer, feature) {

        if (selectedLayer) {

            countriesLayer.resetStyle(selectedLayer);

        }

        selectedLayer = layer;

        layer.setStyle(getSelectedStyle());

        if (layer.bringToFront) {

            layer.bringToFront();

        }

        const name = getCountryName(feature);

        regionName.textContent = name;

        regionDescription.textContent =
            "Географическая территория на мировой карте SIgame. " +
            "В дальнейшем здесь появятся игровые характеристики, " +
            "владелец, армия и возможность захвата.";

        regionOwner.textContent = "Нейтральная территория";

        regionArmy.textContent = "Пока нет данных";

        regionPrice.textContent = "Будет рассчитана";

        regionPanel.classList.add("visible");

    }


    /* ==========================================
       6. ОБРАБОТКА КАЖДОЙ СТРАНЫ
       ========================================== */

    function onEachCountry(feature, layer) {

        const name = getCountryName(feature);

        layer.on({

            mouseover: function () {

                if (layer !== selectedLayer) {

                    layer.setStyle({

                        color: "#e3edf4",

                        weight: 1.5,

                        fillColor: "#6b8b9e",

                        fillOpacity: 0.5

                    });

                }

            },

            mouseout: function () {

                if (layer !== selectedLayer && countriesLayer) {

                    countriesLayer.resetStyle(layer);

                }

            },

            click: function () {

                selectCountry(layer, feature);

            }

        });


        /* Подсказка при наведении */
        layer.bindTooltip(name, {

            sticky: true,

            direction: "top",

            opacity: 0.95

        });

    }


    /* ==========================================
       7. ЗАГРУЗКА ГЕОГРАФИЧЕСКИХ ГРАНИЦ
       ========================================== */

    async function loadCountries() {

        mapStatus.textContent = "Загрузка границ...";

        /*
         * Источник открытых географических данных.
         * Пока используются границы стран.
         */

        const geoJsonUrl =
            "https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson";


        try {

            const response = await fetch(geoJsonUrl);

            if (!response.ok) {

                throw new Error(
                    "Не удалось загрузить границы: HTTP " +
                    response.status
                );

            }

            const geoData = await response.json();

            if (
                !geoData ||
                !Array.isArray(geoData.features) ||
                geoData.features.length === 0
            ) {

                throw new Error(
                    "Источник не содержит географических объектов."
                );

            }


            /* Создаём слой стран */

            countriesLayer = L.geoJSON(geoData, {

                style: getCountryStyle,

                onEachFeature: onEachCountry

            }).addTo(map);


            countriesLoaded = geoData.features.length;

            regionsCount.textContent = countriesLoaded;

            mapStatus.textContent =
                "Территорий: " + countriesLoaded;


            /*
             * Показываем весь мир.
             * Ограничение масштаба не позволяет случайно
             * улететь далеко за пределы карты.
             */

            map.setView([25, 10], 2);


        } catch (error) {

            console.error(
                "Ошибка загрузки карты SIgame:",
                error
            );

            mapStatus.textContent = "Ошибка загрузки границ";

            regionsCount.textContent = "—";

            const errorBox = document.createElement("div");

            errorBox.className = "map-error";

            errorBox.innerHTML = `
                <strong>Не удалось загрузить границы стран.</strong>
                <p>
                    Проверь подключение к интернету и обнови страницу.
                    Если ошибка повторяется, потребуется проверить
                    доступность источника географических данных.
                </p>
            `;

            document.getElementById("world-map").appendChild(errorBox);

        }

    }


    /* ==========================================
       8. ЗАКРЫТИЕ ИНФОРМАЦИОННОЙ ПАНЕЛИ
       ========================================== */

    closePanelButton.addEventListener("click", function () {

        regionPanel.classList.remove("visible");

        if (selectedLayer && countriesLayer) {

            countriesLayer.resetStyle(selectedLayer);

            selectedLayer = null;

        }

    });


    /* ==========================================
       9. КНОПКА ВХОДА
       ========================================== */

    document.getElementById("login-button")
        .addEventListener("click", function () {

            alert(
                "Авторизация через Discord будет добавлена " +
                "на следующем этапе разработки SIgame."
            );

        });


    /* ==========================================
       10. ЗАПУСК
       ========================================== */

    loadCountries();

});