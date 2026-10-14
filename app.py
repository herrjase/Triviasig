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

NEUTRAL_OWNER = "Нейтральная территория"
DEFAULT_PLAYER_COLOR = "#808080"
DEFAULT_TEAM_COLOR = "#808080"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#808080'
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            personal_color TEXT NOT NULL DEFAULT '#808080',
            team_id INTEGER,
            FOREIGN KEY (team_id)
                REFERENCES teams(id)
                ON DELETE SET NULL
        )
    """)

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

    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(regions)"
        ).fetchall()
    }

    if "owner_player_id" not in columns:
        connection.execute("""
            ALTER TABLE regions
            ADD COLUMN owner_player_id INTEGER
            REFERENCES players(id)
            ON DELETE SET NULL
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


def create_test_players(connection):
    """Создаёт тестовые команды и игроков."""

    # Тестовые команды.
    connection.execute("""
        INSERT OR IGNORE INTO teams (name, color)
        VALUES ('Зелёные', '#00aa00')
    """)

    connection.execute("""
        INSERT OR IGNORE INTO teams (name, color)
        VALUES ('Фиолетовые', '#800080')
    """)

    teams = {
        row["name"]: row["id"]
        for row in connection.execute(
            "SELECT id, name FROM teams"
        ).fetchall()
    }

    # Имя, личный цвет, команда, занятые регионы.
    test_players = [
        ("Шикан", "#ff0000", None, ["SIG-3126"]),
        (
            "Котокей",
            "#00aa00",
            teams["Зелёные"],
            ["SIG-2542", "SIG-0922"]
        ),
        (
            "PeterSheff",
            "#0000ff",
            teams["Зелёные"],
            ["SIG-2518"]
        ),
        (
            "ШИЗГИС",
            "#800080",
            teams["Фиолетовые"],
            ["SIG-1473"]
        ),
    ]

    for username, color, team_id, region_ids in test_players:
        connection.execute("""
            INSERT INTO players (
                username,
                personal_color,
                team_id
            )
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                personal_color = excluded.personal_color,
                team_id = excluded.team_id
        """, (username, color, team_id))

        player = connection.execute("""
            SELECT id
            FROM players
            WHERE username = ?
        """, (username,)).fetchone()

        for region_id in region_ids:
            numeric_id = int(region_id.replace("SIG-", ""))

            connection.execute("""
                UPDATE regions
                SET owner_player_id = ?,
                    owner = ?
                WHERE id = ?
            """, (player["id"], username, numeric_id))

    connection.commit()


def synchronize_regions(data):
    connection = get_db()

    try:
        # Добавляем регионы, не перезаписывая существующие записи.
        for feature in data["features"]:
            properties = feature.get("properties") or {}

            name = get_region_name(properties)
            country = get_country_name(properties)
            source_key = get_source_key(feature)

            connection.execute("""
                INSERT OR IGNORE INTO regions (
                    source_key,
                    name,
                    country
                )
                VALUES (?, ?, ?)
            """, (source_key, name, country))

        connection.commit()

        # Создаём тестовые команды и игроков.
        # Их данные сохраняются в SQLite.
        create_test_players(connection)

        for feature in data["features"]:
            properties = feature.get("properties") or {}
            source_key = get_source_key(feature)

            row = connection.execute("""
                SELECT
                    regions.id,
                    regions.owner,
                    regions.owner_player_id,
                    regions.army,
                    regions.price,
                    players.username,
                    players.personal_color,
                    teams.id AS team_id,
                    teams.name AS team_name,
                    teams.color AS team_color
                FROM regions
                LEFT JOIN players
                    ON players.id = regions.owner_player_id
                LEFT JOIN teams
                    ON teams.id = players.team_id
                WHERE regions.source_key = ?
            """, (source_key,)).fetchone()

            properties["region_id"] = (
                "SIG-" + str(row["id"]).zfill(4)
            )

            # Имя владельца всегда остаётся именем игрока.
            if row["username"]:
                properties["owner"] = row["username"]
            else:
                properties["owner"] = (
                    row["owner"] or NEUTRAL_OWNER
                )

            properties["owner_player_id"] = (
                row["owner_player_id"]
            )

            properties["army"] = row["army"] or 0
            properties["price"] = row["price"] or 0

            # Личный цвет игрока.
            properties["player_color"] = (
                row["personal_color"] or DEFAULT_PLAYER_COLOR
            ) if row["username"] else None

            # Цвет и название команды.
            properties["team_id"] = row["team_id"]
            properties["team_name"] = row["team_name"]
            properties["team_color"] = row["team_color"]

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