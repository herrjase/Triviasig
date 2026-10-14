import os
import json
import sqlite3
import hashlib
import urllib.request

from flask import Flask, render_template, jsonify

app = Flask(__name__)

REGIONS_URL = (
    "https://gtamapdata.org/data/web/global_adm1_2020.geojson"
)

os.makedirs(app.instance_path, exist_ok=True)

DB_PATH = os.path.join(app.instance_path, "sigame.db")
CACHE_PATH = os.path.join(app.instance_path, "regions.geojson")


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    connection.execute("""
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            country TEXT NOT NULL,
            owner TEXT DEFAULT 'Нейтральная территория',
            army INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0
        )
    """)

    connection.commit()
    return connection


def get_region_data():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as file:
            return json.load(file)

    request = urllib.request.Request(
        REGIONS_URL,
        headers={"User-Agent": "SIgame/1.0"}
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    if not isinstance(data.get("features"), list):
        raise ValueError("Источник не содержит список регионов")

    with open(CACHE_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)

    return data


def get_region_name(properties):
    return (
        properties.get("name")
        or properties.get("NAME")
        or properties.get("NAME_1")
        or properties.get("region")
        or properties.get("admin1")
        or properties.get("shapeName")
        or "Неизвестный регион"
    )


def get_country_name(properties):
    return (
        properties.get("admin")
        or properties.get("country")
        or properties.get("country_name")
        or properties.get("ADMIN")
        or properties.get("NAME_0")
        or properties.get("iso3")
        or properties.get("ISO3")
        or "Страна не указана"
    )


def get_source_key(feature):
    properties = feature.get("properties") or {}

    identity = {
        "name": get_region_name(properties),
        "country": get_country_name(properties),
        "geometry": feature.get("geometry")
    }

    encoded = json.dumps(
        identity,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def synchronize_regions(data):
    connection = get_db()

    try:
        for feature in data["features"]:
            properties = feature.get("properties") or {}

            name = get_region_name(properties)
            country = get_country_name(properties)
            source_key = get_source_key(feature)

            connection.execute("""
                INSERT OR IGNORE INTO regions
                    (source_key, name, country)
                VALUES (?, ?, ?)
            """, (source_key, name, country))

        connection.commit()

        for feature in data["features"]:
            properties = feature.get("properties") or {}
            source_key = get_source_key(feature)

            row = connection.execute(
                "SELECT * FROM regions WHERE source_key = ?",
                (source_key,)
            ).fetchone()

            properties["region_id"] = (
                "SIG-" + str(row["id"]).zfill(4)
            )
            properties["owner"] = row["owner"]
            properties["army"] = row["army"]
            properties["price"] = row["price"]

            feature["properties"] = properties

        return data

    finally:
        connection.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/regions")
def api_regions():
    try:
        data = get_region_data()
        data = synchronize_regions(data)
        return jsonify(data)

    except Exception as error:
        app.logger.exception("Не удалось загрузить регионы")
        return jsonify({
            "error": "Не удалось загрузить регионы",
            "details": str(error)
        }), 500


@app.route("/profile")
def profile():
    return render_template("profile.html")


@app.route("/army")
def army():
    return render_template("army.html")


@app.route("/regions")
def regions():
    return render_template("regions.html")


@app.route("/mercenaries")
def mercenaries():
    return render_template("mercenaries.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/rating")
def rating():
    return render_template("rating.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8000,
        debug=True
    )