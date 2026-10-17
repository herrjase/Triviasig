import argparse
import csv
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "sigame.db"
REPORT_PATH = BASE_DIR / "data" / "population_match_report.csv"

POPULATION_CANDIDATES = [
    "population",
    "population_count",
    "total_population",
    "pop_total",
    "pop",
    "population_sum",
    "sum",
    "ghsl_population",
    "ghsl_pop",
    "value",
]

COUNTRY_CANDIDATES = [
    "country",
    "country_name",
    "admin0",
    "admin0_name",
    "shape_group",
    "adm0_name",
    "name_0",
]

REGION_CANDIDATES = [
    "region",
    "region_name",
    "admin1",
    "admin1_name",
    "shape_name",
    "adm1_name",
    "name_1",
    "name",
]

YEAR_CANDIDATES = [
    "year",
    "population_year",
    "reference_year",
    "data_year",
]


def normalize(value):
    """Нормализует текст для сопоставления названий."""
    if value is None:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    text = text.casefold().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-zа-яё0-9]+", " ", text)
    return " ".join(text.split())


def find_field(columns, candidates):
    """Ищет поле без учёта регистра."""
    lookup = {
        str(column).casefold(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]

    return None


def parse_population(value):
    """Возвращает целое население или None."""
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number < 0 or number != number:
        return None

    if number == float("inf") or number == float("-inf"):
        return None

    return int(round(number))


def parse_year(value):
    if value is None:
        return None

    try:
        year = int(float(value))
    except (TypeError, ValueError):
        return None

    if 1800 <= year <= 2200:
        return year

    return None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Импорт населения в Triviasig "
            "с безопасным сопоставлением регионов."
        )
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Путь к исходному файлу .fgb, .geojson или другому "
             "поддерживаемому GeoPandas формату.",
    )

    parser.add_argument(
        "--population-field",
        help="Название поля с населением.",
    )

    parser.add_argument(
        "--country-field",
        help="Название поля со страной.",
    )

    parser.add_argument(
        "--region-field",
        help="Название поля с названием региона.",
    )

    parser.add_argument(
        "--year-field",
        help="Название поля с годом оценки населения.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать результаты в базу. Без этого флага работает "
             "только проверка.",
    )

    args = parser.parse_args()

    source_path = Path(args.source).expanduser()

    if not source_path.is_absolute():
        source_path = BASE_DIR / source_path

    if not source_path.exists():
        sys.exit(f"Файл набора не найден: {source_path}")

    if not DB_PATH.exists():
        sys.exit(
            f"База игры не найдена: {DB_PATH}\n"
            "Сначала запусти проект, чтобы создать базу."
        )

    print("Читаю демографический набор...")

    try:
        data = gpd.read_file(source_path)
    except Exception as error:
        sys.exit(
            "Не удалось прочитать демографический файл.\n"
            f"Ошибка: {error}"
        )

    if data.empty:
        sys.exit("Демографический набор пуст.")

    columns = list(data.columns)

    print("\nПоля исходного набора:")
    for column in columns:
        print(f"  - {column}")

    population_field = (
        args.population_field
        or find_field(columns, POPULATION_CANDIDATES)
    )

    country_field = (
        args.country_field
        or find_field(columns, COUNTRY_CANDIDATES)
    )

    region_field = (
        args.region_field
        or find_field(columns, REGION_CANDIDATES)
    )

    year_field = (
        args.year_field
        or find_field(columns, YEAR_CANDIDATES)
    )

    missing = []

    if population_field not in columns:
        missing.append("поле населения (--population-field)")

    if country_field not in columns:
        missing.append("поле страны (--country-field)")

    if region_field not in columns:
        missing.append("поле региона (--region-field)")

    if missing:
        sys.exit(
            "\nНе удалось однозначно определить: "
            + ", ".join(missing)
            + "\nПосмотри список полей выше и укажи их явно."
        )

    print("\nВыбранные поля:")
    print(f"  Страна:    {country_field}")
    print(f"  Регион:    {region_field}")
    print(f"  Население: {population_field}")
    print(f"  Год:       {year_field or 'не указан'}")

    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(regions)"
            )
        }

        required_columns = {
            "id",
            "name",
            "country",
        }

        if not required_columns.issubset(existing_columns):
            sys.exit(
                "Структура таблицы regions отличается от ожидаемой. "
                "База не изменена."
            )

        regions = connection.execute(
            """
            SELECT id, name, country
            FROM regions
            """
        ).fetchall()

    if not regions:
        sys.exit("В игровой базе нет регионов.")

    # Собираем индексы существующих регионов по стране и названию.
    region_index = {}

    for region in regions:
        key = (
            normalize(region["country"]),
            normalize(region["name"]),
        )

        if not all(key):
            continue

        region_index.setdefault(key, []).append(region["id"])

    # Подготавливаем записи демографического набора.
    population_index = {}
    invalid_population = 0
    invalid_names = 0

    for _, row in data.iterrows():
        country = normalize(row[country_field])
        name = normalize(row[region_field])
        population = parse_population(row[population_field])

        if not country or not name:
            invalid_names += 1
            continue

        if population is None:
            invalid_population += 1
            continue

        year = (
            parse_year(row[year_field])
            if year_field
            else None
        )

        key = (country, name)

        # Несколько записей с одинаковым ключом неоднозначны.
        population_index.setdefault(key, []).append({
            "population": population,
            "year": year,
            "country_original": str(row[country_field]),
            "region_original": str(row[region_field]),
        })

    report_rows = []
    updates = []
    matched_ids = set()

    for region in regions:
        region_id = region["id"]

        key = (
            normalize(region["country"]),
            normalize(region["name"]),
        )

        candidates = population_index.get(key, [])

        if not candidates:
            report_rows.append({
                "region_id": region_id,
                "country": region["country"],
                "region": region["name"],
                "status": "not_found",
                "population": "",
                "year": "",
                "details": "Совпадение по стране и названию не найдено",
            })
            continue

        if len(candidates) > 1:
            report_rows.append({
                "region_id": region_id,
                "country": region["country"],
                "region": region["name"],
                "status": "ambiguous",
                "population": "",
                "year": "",
                "details": (
                    f"Найдено записей источника: {len(candidates)}"
                ),
            })
            continue

        candidate = candidates[0]

        updates.append((
            candidate["population"],
            candidate["year"],
            "UNDP Admin 1 Population",
            region_id,
        ))

        matched_ids.add(key)

        report_rows.append({
            "region_id": region_id,
            "country": region["country"],
            "region": region["name"],
            "status": "matched",
            "population": candidate["population"],
            "year": candidate["year"] or "",
            "details": "Точное совпадение нормализованных названий",
        })

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with REPORT_PATH.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "region_id",
                "country",
                "region",
                "status",
                "population",
                "year",
                "details",
            ],
        )

        writer.writeheader()
        writer.writerows(report_rows)

    matched = sum(
        1 for row in report_rows
        if row["status"] == "matched"
    )

    not_found = sum(
        1 for row in report_rows
        if row["status"] == "not_found"
    )

    ambiguous = sum(
        1 for row in report_rows
        if row["status"] == "ambiguous"
    )

    print("\nРезультаты сопоставления:")
    print(f"  Регионов в игре: {len(regions)}")
    print(f"  Найдено совпадений: {matched}")
    print(f"  Не найдено: {not_found}")
    print(f"  Неоднозначных совпадений: {ambiguous}")
    print(f"  Пропущено записей без названий: {invalid_names}")
    print(f"  Записей с некорректным населением: {invalid_population}")
    print(f"  Отчёт: {REPORT_PATH}")

    if not args.apply:
        print("\nПРОВЕРКА ЗАВЕРШЕНА. БАЗА НЕ ИЗМЕНЕНА.")
        print(
            "Проверь отчёт. Если сопоставление корректно, "
            "повтори команду с флагом --apply."
        )
        return

    # Добавляем только новые демографические столбцы.
    # Существующие игровые поля не переписываем.
    with sqlite3.connect(DB_PATH) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")

            existing_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(regions)"
                )
            }

            if "population" not in existing_columns:
                connection.execute(
                    "ALTER TABLE regions ADD COLUMN population INTEGER"
                )

            if "population_year" not in existing_columns:
                connection.execute(
                    "ALTER TABLE regions ADD COLUMN population_year INTEGER"
                )

            if "population_source" not in existing_columns:
                connection.execute(
                    "ALTER TABLE regions ADD COLUMN population_source TEXT"
                )

            # Обновляем исключительно три демографических поля.
            # Владельцы, армии, цены и другие параметры не затрагиваются.
            connection.executemany(
                """
                UPDATE regions
                SET population = ?,
                    population_year = ?,
                    population_source = ?
                WHERE id = ?
                """,
                updates,
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    print("\nИМПОРТ ЗАВЕРШЁН.")
    print(f"Обновлено регионов: {len(updates)}")
    print("Игровые параметры не изменялись.")


if __name__ == "__main__":
    main()