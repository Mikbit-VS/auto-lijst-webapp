# Autolijst

Kleine Flask-app om auto’s te beheren via de browser.

- Opslag: `auto_lijst.db` (SQLite)
- Eenmalige migratie: als `auto_lijst.db` nog niet bestaat en `auto_lijst.xlsx` wel, dan wordt data automatisch overgezet.

## Vereisten

- Python 3.13 (of vergelijkbaar)
- `pip`

## Installatie

1. Open een terminal in deze map.
2. (Optioneel) Maak een virtuele omgeving:

```powershell
python -m venv .venv
```

3. Activeer de virtuele omgeving:

```powershell
.\.venv\Scripts\Activate.ps1
```

4. Installeer dependencies:

```powershell
pip install -r requirements.txt
```

## App starten

```powershell
python app.py
```

Daarna openen in je browser:

- http://127.0.0.1:5000

## Als echte webapp draaien (productie)

Gebruik voor productie een WSGI-server in plaats van Flask debug server.

### Lokaal productie-achtig starten

```powershell
python -m waitress --host=0.0.0.0 --port=8000 app:app
```

Daarna openen:

- http://127.0.0.1:8000

### Deployen (bijv. Render of Railway)

Dit project bevat een `Procfile`:

- `web: waitress-serve --host=0.0.0.0 --port=$PORT app:app`

Algemene stappen:

1. Push de map naar GitHub.
2. Maak een nieuwe Web Service op Render/Railway.
3. Build/install command: `pip install -r requirements.txt`
4. Start command: automatisch via `Procfile` (of handmatig dezelfde regel).

Belangrijk:

- De app gebruikt `auto_lijst.db` als lokale database.
- Op sommige cloudplatformen is lokale schijfopslag tijdelijk; gebruik dan een externe database als data permanent moet blijven.

## Functionaliteit

Via de webpagina kun je:

- een nieuwe rij toevoegen;
- bestaande rijen bewerken via de knop **Bewerk**;
- rijen verwijderen.

Daarnaast:

- paginering op de overzichtspagina;
- automatische `Categorie` op basis van `Bouwjaar`:
  - `< 1990` → `Klassieker`
  - `>= 1990` → `Youngtimer`

## Veelvoorkomende fouten

- `ModuleNotFoundError`:
  - Controleer of je venv actief is.
  - Voer opnieuw uit: `pip install -r requirements.txt`

- Migratie vanaf Excel lukt niet:
  - Controleer of `auto_lijst.xlsx` in dezelfde map staat als `app.py`.
  - Controleer of het bestand leesbaar is.

## Beheer-checklist (live)

### Dagelijks (30 sec)

1. Open de app en test één actie (bijv. toevoegen of bewerken).
2. Controleer live versie:

```text
https://auto-lijst-webapp.onrender.com/version
```

### Bij elke codewijziging

```powershell
git status
git add .
git commit -m "Korte, duidelijke wijziging"
git push
```

Controleer daarna in Render of de nieuwste deploy status **Live** is.

### Backup & herstel

- Maak periodiek een backup van `auto_lijst.db`.
- Zet Render alerts aan voor mislukte deploys.
- Gebruik bij problemen een rollback naar de vorige succesvolle deploy.

## Incident-procedure

### 1) Site geeft `500 Internal Server Error`

1. Open Render → service → **Logs**.
2. Zoek de eerste traceback/foutregel.
3. Vergelijk live versie via `/version` met je laatste commit.
4. Als nodig: rollback naar vorige succesvolle deploy.

### 2) Site laadt, maar data lijkt leeg

1. Controleer of de juiste opslag gebruikt wordt (`auto_lijst.db`).
2. Controleer of een recente deploy niet op een lege runtime-schijf is gestart.
3. Herstel data vanuit je laatste backup.

### 3) Nieuwe push is niet live

1. Controleer op GitHub of de commit op `main` staat.
2. Controleer in Render of die commit gedeployed is.
3. Start handmatig: **Manual Deploy → Deploy latest commit**.

### 4) Snelle basischeck na herstel

1. Open homepage.
2. Test 1x toevoegen en 1x bewerken.
3. Controleer `/version`.
