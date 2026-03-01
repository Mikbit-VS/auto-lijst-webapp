from pathlib import Path
import os
import re
import sqlite3
import subprocess

from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import pandas as pd

app = Flask(__name__)
excel_path = Path(__file__).with_name("auto_lijst.xlsx")
db_path = Path(__file__).with_name("auto_lijst.db")
static_path = Path(__file__).with_name("static")
table_name = "autos"
default_columns = ["Merk", "Type", "Bouwjaar", "Prijs", "Categorie"]


def get_app_version() -> str:
    env_version = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT")
    if env_version:
        return env_version[:7]

    try:
        output = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return output.decode("utf-8").strip()
    except Exception:
        return "unknown"


def get_header_image_url() -> str | None:
    candidates = [
        "porsche911cabrio.jpg",
    ]

    for filename in candidates:
        if (static_path / filename).exists():
            return url_for("static", filename=filename)

    return None


def ensure_category_column(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    changed = False

    if "Categorie" not in df.columns:
        df["Categorie"] = ""
        changed = True

    if "Categorie" in df.columns and df["Categorie"].dtype != object:
        df["Categorie"] = df["Categorie"].astype("object")
        changed = True

    ordered_columns = [column for column in df.columns if column != "Categorie"] + ["Categorie"]
    if list(df.columns) != ordered_columns:
        df = df[ordered_columns]
        changed = True

    return df, changed


def parse_bouwjaar(value) -> int | None:
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    text = str(value).strip()
    match = re.search(r"(19\d{2}|20\d{2})", text)
    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def determine_category_from_bouwjaar(bouwjaar_value) -> str:
    year = parse_bouwjaar(bouwjaar_value)
    if year is None:
        return ""
    return "Klassieker" if year < 1990 else "Youngtimer"


def apply_category_rules(df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    if "Bouwjaar" not in df.columns or "Categorie" not in df.columns:
        return df, False

    changed = False
    for row_index in df.index:
        new_category = determine_category_from_bouwjaar(df.at[row_index, "Bouwjaar"])
        current_category = "" if pd.isna(df.at[row_index, "Categorie"]) else str(df.at[row_index, "Categorie"])
        if current_category != new_category:
            df.at[row_index, "Categorie"] = new_category
            changed = True

    return df, changed


def render_file_locked_message(action_label: str):
    return (
        render_template_string(
            """
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    background: #f6f8fb;
                    color: #1f2937;
                }
                .container {
                    max-width: 760px;
                    margin: 32px auto;
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 24px;
                }
                .warn {
                    background: #fff7ed;
                    border: 1px solid #fdba74;
                    border-radius: 8px;
                    padding: 12px;
                    margin-top: 10px;
                }
                a {
                    display: inline-block;
                    margin-top: 14px;
                    text-decoration: none;
                    color: #1d4ed8;
                }
            </style>
            <div class="container">
                <h1>Opslaan lukt niet</h1>
                <div class="warn">
                    De wijziging ({{ action_label }}) kon niet worden opgeslagen.
                </div>
                <p>Probeer het opnieuw. Als het probleem blijft, herstart de app.</p>
                <a href="{{ url_for('home') }}">← Terug naar overzicht</a>
            </div>
            """,
            action_label=action_label,
        ),
        409,
    )


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    )
    return cursor.fetchone() is not None


def load_dataframe() -> pd.DataFrame:
    if not db_path.exists() and excel_path.exists():
        try:
            migrated = pd.read_excel(excel_path)
            migrated, _ = ensure_category_column(migrated)
            migrated, _ = apply_category_rules(migrated)
            save_dataframe(migrated)
        except Exception:
            pass

    if not db_path.exists():
        return pd.DataFrame(columns=default_columns)

    with sqlite3.connect(db_path) as connection:
        if not table_exists(connection, table_name):
            return pd.DataFrame(columns=default_columns)

        query = f'SELECT "Merk", "Type", "Bouwjaar", "Prijs", "Categorie" FROM "{table_name}" ORDER BY id'
        df = pd.read_sql_query(query, connection)

    return df


def save_dataframe(df: pd.DataFrame) -> None:
    df, _ = ensure_category_column(df)
    df, _ = apply_category_rules(df)

    for column in default_columns:
        if column not in df.columns:
            df[column] = ""

    df = df[default_columns].copy()
    df = df.fillna("")
    for column in default_columns:
        df[column] = df[column].astype(str)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                "Merk" TEXT,
                "Type" TEXT,
                "Bouwjaar" TEXT,
                "Prijs" TEXT,
                "Categorie" TEXT
            )
            '''
        )
        connection.execute(f'DELETE FROM "{table_name}"')
        insert_sql = f'INSERT INTO "{table_name}" ("Merk", "Type", "Bouwjaar", "Prijs", "Categorie") VALUES (?, ?, ?, ?, ?)'
        connection.executemany(insert_sql, df[default_columns].itertuples(index=False, name=None))
        connection.commit()


def format_eur_value(value) -> str:
    if pd.isna(value):
        return ""

    if isinstance(value, str):
        cleaned = (
            value.strip()
            .replace("€", "")
            .replace(" ", "")
            .replace(".-", "")
            .replace(",-", "")
            .replace(".", "")
            .replace(",", ".")
        )
    else:
        cleaned = str(value)

    try:
        number = float(cleaned)
    except ValueError:
        return str(value)

    if number.is_integer():
        thousands = f"{int(number):,}".replace(",", ".")
        return f"€ {thousands},-"

    formatted = f"{number:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"€ {formatted}"


def to_display_value(value, column_name: str | None = None, format_price: bool = False) -> str:
    if pd.isna(value):
        return ""

    if format_price and column_name and column_name.strip().lower() == "prijs":
        return format_eur_value(value)

    return str(value)


def parse_positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return parsed if parsed > 0 else default

@app.route("/")
def home():
    df = load_dataframe()
    app_version = get_app_version()
    header_image_url = get_header_image_url()

    if df.empty and len(df.columns) == 0:
        return render_template_string(
            """
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    background: #f6f8fb;
                    color: #1f2937;
                }
                .container {
                    max-width: 900px;
                    margin: 32px auto;
                    background: white;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 24px;
                }
                h1 {
                    margin-top: 0;
                }
                .version {
                    color: #6b7280;
                    font-size: 0.85rem;
                }
                .page-head {
                    display: flex;
                    align-items: flex-start;
                    gap: 14px;
                }
                .brand-image {
                    width: 220px;
                    max-width: 38vw;
                    height: auto;
                    border-radius: 10px;
                    object-fit: cover;
                    border: 1px solid #e5e7eb;
                }
            </style>

            <div class="container">
                <div class="page-head">
                    {% if header_image_url %}
                        <img src="{{ header_image_url }}" alt="Auto" class="brand-image">
                    {% endif %}
                    <div>
                        <h1>Autolijst</h1>
                        <p class="version">Versie: {{ app_version }}</p>
                    </div>
                </div>
                <p>Er is nog geen data gevonden.</p>
                <p>Plaats eventueel <strong>auto_lijst.xlsx</strong> in dezelfde map als <strong>app.py</strong> voor een eenmalige migratie.</p>
            </div>
            """,
            app_version=app_version,
            header_image_url=header_image_url,
        )

    df, _ = ensure_category_column(df)
    df, _ = apply_category_rules(df)
    columns = list(df.columns)
    editable_columns = [column for column in columns if column != "Categorie"]
    total_rows = len(df)
    page = parse_positive_int(request.args.get("page"), 1)
    per_page = parse_positive_int(request.args.get("per_page"), 50)
    per_page = min(per_page, 500)

    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    page = min(page, total_pages)

    start = (page - 1) * per_page
    end = min(start + per_page, total_rows)

    records = []
    for row_index in range(start, end):
        row_data = {
            column: to_display_value(
                df.iloc[row_index][column],
                column_name=column,
                format_price=True,
            )
            for column in columns
        }
        records.append({"index": row_index, "display_index": row_index + 1, "data": row_data})

    return render_template_string(
        """
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                background: #f6f8fb;
                color: #1f2937;
            }
            .container {
                max-width: 1000px;
                margin: 28px auto;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 24px;
            }
            h1 {
                margin-top: 0;
                margin-bottom: 18px;
            }
            .version {
                color: #6b7280;
                font-size: 0.85rem;
                margin-top: -8px;
                margin-bottom: 0;
            }
            .top-layout {
                display: flex;
                align-items: stretch;
                gap: 22px;
                margin-bottom: 24px;
            }
            .brand-panel {
                width: 280px;
                flex: 0 0 280px;
                display: flex;
            }
            .page-head {
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                height: 100%;
                width: 100%;
            }
            .brand-image {
                width: 100%;
                max-width: 250px;
                height: auto;
                margin-top: 12px;
                border-radius: 10px;
                object-fit: cover;
                border: 1px solid #e5e7eb;
            }
            @media (max-width: 1000px) {
                .top-layout {
                    flex-direction: column;
                }
                .brand-panel {
                    width: 100%;
                    flex: 1 1 auto;
                }
                .brand-image {
                    max-width: 380px;
                }
            }
            h2 {
                margin: 0;
                font-size: 1.2rem;
            }
            .data-table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 18px;
                font-size: 0.92rem;
            }
            .data-table th,
            .data-table td {
                border: 1px solid #d1d5db;
                padding: 8px;
                text-align: left;
                vertical-align: top;
            }
            .data-table th {
                background: #f3f4f6;
                color: #111827;
            }
            .field {
                margin-bottom: 10px;
            }
            .add-section {
                border: 2px solid #bfdbfe;
                background: #eff6ff;
                border-radius: 10px;
                padding: 16px;
                margin-bottom: 0;
                flex: 1 1 auto;
            }
            .add-title {
                margin: 0 0 6px;
                font-size: 1.05rem;
                color: #1e3a8a;
            }
            .add-help {
                margin: 0 0 14px;
                font-size: 0.9rem;
                color: #334155;
            }
            .add-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(220px, 1fr));
                gap: 10px 14px;
            }
            @media (max-width: 700px) {
                .add-grid {
                    grid-template-columns: 1fr;
                }
                .add-section {
                    max-width: 100%;
                }
            }
            label {
                display: block;
                font-size: 0.92rem;
                margin-bottom: 4px;
            }
            input[type="text"] {
                width: 100%;
                max-width: 420px;
                padding: 8px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                box-sizing: border-box;
            }
            .per-page-form input.per-page-input {
                width: 80px;
                max-width: 80px;
            }
            button {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                cursor: pointer;
            }
            .small-btn {
                padding: 6px 10px;
                font-size: 0.85rem;
                text-decoration: none;
                display: inline-block;
                border-radius: 6px;
                background: #2563eb;
                color: white;
            }
            .add-submit {
                margin-top: 6px;
                font-size: 0.9rem;
            }
            .per-page-submit {
                padding: 8px 12px;
                font-size: 0.9rem;
                border: none;
            }
            .delete-btn {
                background: #dc2626;
            }
            .inline-form {
                display: inline;
            }
            .toolbar {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 12px;
                margin: 8px 0 6px;
            }
            .toolbar-left {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }
            .toolbar-right {
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 4px;
            }
            .per-page-form {
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 4px;
            }
            .per-page-controls {
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .per-page-form label {
                margin-bottom: 0;
            }
            .per-page-input {
                width: 80px;
                max-width: 80px;
                display: inline-block;
            }
            .meta {
                color: #4b5563;
                font-size: 0.92rem;
            }
            .pager {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-top: 12px;
            }
            .pager a {
                text-decoration: none;
                color: #1d4ed8;
            }
        </style>

        <div class="container">
            <div class="top-layout">
                <div class="brand-panel">
                    <div class="page-head">
                        <div>
                            <h1>Autolijst</h1>
                            <div class="version">Versie: {{ app_version }}</div>
                        </div>
                        {% if header_image_url %}
                            <img src="{{ header_image_url }}" alt="Auto" class="brand-image">
                        {% endif %}
                    </div>
                </div>

                <div class="add-section">
                    <h3 class="add-title">Nieuwe auto invoeren</h3>
                    <p class="add-help">Vul de velden in en klik op Toevoegen om direct een nieuwe rij op te slaan.</p>
                    <form method="post" action="{{ url_for('add_row') }}">
                        <input type="hidden" name="page" value="{{ page }}">
                        <input type="hidden" name="per_page" value="{{ per_page }}">
                        <div class="add-grid">
                            {% for column in editable_columns %}
                                <div class="field">
                                    <label>{{ column }}</label>
                                    <input type="text" name="{{ column }}">
                                </div>
                            {% endfor %}
                        </div>
                        <button type="submit" class="add-submit">Toevoegen</button>
                    </form>
                </div>
            </div>

            <div class="toolbar">
                <div class="toolbar-left">
                    <h2>Overzicht</h2>
                    <div class="meta">Totaal rijen: <strong>{{ total_rows }}</strong></div>
                </div>
                <div class="toolbar-right">
                    <form method="get" action="{{ url_for('home') }}" class="per-page-form">
                        <label for="per_page">Rijen per pagina</label>
                        <div class="per-page-controls">
                            <input id="per_page" type="text" name="per_page" value="{{ per_page }}" class="per-page-input">
                            <input type="hidden" name="page" value="1">
                            <button type="submit" class="per-page-submit">Toon</button>
                        </div>
                    </form>
                </div>
            </div>

            <table class="data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        {% for column in columns %}
                            <th>{{ column }}</th>
                        {% endfor %}
                        <th>Acties</th>
                    </tr>
                </thead>
                <tbody>
                    {% if records %}
                        {% for record in records %}
                            <tr>
                                <td>{{ record.display_index }}</td>
                                {% for column in columns %}
                                    <td>{{ record.data[column] }}</td>
                                {% endfor %}
                                <td>
                                    <a href="{{ url_for('edit_row', row_index=record.index, page=page, per_page=per_page) }}" class="small-btn">Bewerk</a>
                                    <form method="post" action="{{ url_for('delete_row', row_index=record.index) }}" class="inline-form">
                                        <input type="hidden" name="page" value="{{ page }}">
                                        <input type="hidden" name="per_page" value="{{ per_page }}">
                                        <button type="submit" class="small-btn delete-btn">Verwijder</button>
                                    </form>
                                </td>
                            </tr>
                        {% endfor %}
                    {% else %}
                        <tr>
                            <td colspan="{{ columns|length + 2 }}">Er zijn nog geen rijen aanwezig.</td>
                        </tr>
                    {% endif %}
                </tbody>
            </table>

            <div class="pager">
                {% if page > 1 %}
                    <a href="{{ url_for('home', page=page-1, per_page=per_page) }}">← Vorige</a>
                {% endif %}
                <span>Pagina {{ page }} van {{ total_pages }}</span>
                {% if page < total_pages %}
                    <a href="{{ url_for('home', page=page+1, per_page=per_page) }}">Volgende →</a>
                {% endif %}
            </div>
        </div>
        """,
        columns=columns,
        editable_columns=editable_columns,
        records=records,
        total_rows=total_rows,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        app_version=app_version,
        header_image_url=header_image_url,
    )


@app.route("/version")
def version():
    return jsonify({"version": get_app_version()})


@app.route("/add", methods=["POST"])
def add_row():
    df = load_dataframe()
    if len(df.columns) == 0:
        return redirect(url_for("home"))

    df, _ = ensure_category_column(df)

    new_row = {column: request.form.get(column, "") for column in df.columns}
    df.loc[len(df)] = new_row
    df, _ = apply_category_rules(df)
    try:
        save_dataframe(df)
    except PermissionError:
        return render_file_locked_message("rij toevoegen")
    return redirect(
        url_for(
            "home",
            page=parse_positive_int(request.form.get("page"), 1),
            per_page=parse_positive_int(request.form.get("per_page"), 50),
        )
    )


@app.route("/edit/<int:row_index>", methods=["GET", "POST"])
def edit_row(row_index: int):
    df = load_dataframe()
    df, _ = ensure_category_column(df)
    df, _ = apply_category_rules(df)
    if row_index < 0 or row_index >= len(df):
        return redirect(url_for("home"))

    page = parse_positive_int(request.values.get("page"), 1)
    per_page = parse_positive_int(request.values.get("per_page"), 50)
    editable_columns = [column for column in df.columns if column != "Categorie"]

    if request.method == "POST":
        for column in editable_columns:
            df.at[row_index, column] = request.form.get(column, "")

        df, _ = apply_category_rules(df)

        try:
            save_dataframe(df)
        except PermissionError:
            return render_file_locked_message("rij bewerken")
        return redirect(url_for("home", page=page, per_page=per_page))

    row_data = {
        column: to_display_value(df.iloc[row_index][column])
        for column in df.columns
    }

    return render_template_string(
        """
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                background: #f6f8fb;
                color: #1f2937;
            }
            .container {
                max-width: 800px;
                margin: 28px auto;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 24px;
            }
            .field {
                margin-bottom: 10px;
            }
            label {
                display: block;
                font-size: 0.92rem;
                margin-bottom: 4px;
            }
            input[type="text"] {
                width: 100%;
                max-width: 520px;
                padding: 8px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                box-sizing: border-box;
            }
            button,
            a {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                text-decoration: none;
                cursor: pointer;
                display: inline-block;
                font-size: 0.9rem;
            }
            .actions {
                margin-top: 14px;
                display: flex;
                gap: 8px;
            }
            .back-link {
                background: #4b5563;
            }
        </style>

        <div class="container">
            <h1>Rij {{ row_number }} bewerken</h1>
            <form method="post" action="{{ url_for('edit_row', row_index=row_index) }}">
                <input type="hidden" name="page" value="{{ page }}">
                <input type="hidden" name="per_page" value="{{ per_page }}">
                {% for column in editable_columns %}
                    <div class="field">
                        <label>{{ column }}</label>
                        <input type="text" name="{{ column }}" value="{{ row_data[column] }}">
                    </div>
                {% endfor %}
                <div class="field">
                    <label>Categorie (automatisch)</label>
                    <input type="text" value="{{ row_data['Categorie'] }}" readonly>
                </div>
                <div class="actions">
                    <button type="submit">Opslaan</button>
                    <a href="{{ url_for('home', page=page, per_page=per_page) }}" class="back-link">Terug</a>
                </div>
            </form>
        </div>
        """,
        editable_columns=editable_columns,
        row_data=row_data,
        row_number=row_index + 1,
        row_index=row_index,
        page=page,
        per_page=per_page,
    )


@app.route("/delete/<int:row_index>", methods=["POST"])
def delete_row(row_index: int):
    df = load_dataframe()
    df, _ = ensure_category_column(df)
    df, _ = apply_category_rules(df)
    if row_index < 0 or row_index >= len(df):
        return redirect(url_for("home"))

    df = df.drop(index=row_index).reset_index(drop=True)
    try:
        save_dataframe(df)
    except PermissionError:
        return render_file_locked_message("rij verwijderen")
    return redirect(
        url_for(
            "home",
            page=parse_positive_int(request.form.get("page"), 1),
            per_page=parse_positive_int(request.form.get("per_page"), 50),
        )
    )

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = parse_positive_int(os.getenv("PORT"), 5000)
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)