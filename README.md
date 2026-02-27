# Excel Autolijst

Kleine Flask-app die `auto_lijst.xlsx` uitleest, toont én laat aanpassen via de browser.

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
waitress-serve --host=0.0.0.0 --port=8000 app:app
```

Daarna openen:

- http://127.0.0.1:8000

### Deployen (bijv. Render of Railway)

Dit project bevat nu een `Procfile`:

- `web: waitress-serve --host=0.0.0.0 --port=$PORT app:app`

Algemene stappen:

1. Push de map naar GitHub.
2. Maak een nieuwe Web Service op Render/Railway.
3. Build/install command: `pip install -r requirements.txt`
4. Start command: automatisch via `Procfile` (of handmatig dezelfde regel).

Belangrijk:

- Zorg dat `auto_lijst.xlsx` aanwezig is in de runtime omgeving.
- Op sommige cloudplatformen is lokale schijfopslag tijdelijk; gebruik dan een externe opslag (bijv. database of object storage) als je data permanent moet blijven.

## Wijzigingen doorvoeren via `app.py`

Via de webpagina kun je nu:

- een nieuwe rij toevoegen;
- bestaande rijen bewerken via de knop **Bewerk**;
- rijen verwijderen.

De hoofdpagina gebruikt paginering (instelbaar via **Rijen per pagina**) zodat ook grote bestanden, zoals 10.000+ rijen, werkbaar blijven.

Alle wijzigingen worden direct opgeslagen in `auto_lijst.xlsx`.

## Veelvoorkomende fouten

- `ModuleNotFoundError`:
  - Controleer of je venv actief is.
  - Voer opnieuw uit: `pip install -r requirements.txt`

- Fout op Excel-bestand:
  - Controleer of `auto_lijst.xlsx` in dezelfde map staat als `app.py`.
  - Controleer of het bestand minimaal één kolom bevat.
