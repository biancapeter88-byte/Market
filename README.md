# Market Leadership Dashboard

Dashboard browser-based care calculează 8 scoruri de confluență + Day Type
Predictor + Market Regime, folosind date de la **Twelve Data API**. Nu ai nevoie de cont la broker.

## Deploy pe Render (cloud, gratuit, permanent — recomandat)

Rulează 24/7 în cloud, îl deschizi de pe telefon de oriunde, fără Mac pornit.

**Pas 1 — Pune codul pe GitHub** (fără nevoie de git în terminal):
1. Mergi pe https://github.com/new, creează un repo nou (ex. `market-dashboard`), poate fi privat.
2. Pe pagina repo-ului, click **"uploading an existing file"** (sau drag & drop).
3. Trage întregul folder `market-dashboard/` (backend/, frontend/, render.yaml) peste zona de upload.
4. Commit.

**Pas 2 — Conectează Render la repo:**
1. Pe render.com, click **New +** → **Blueprint**.
2. Selectează repo-ul tău de pe GitHub (Render citește automat `render.yaml`).
3. Creează gratuit o cheie API la https://twelvedata.com (doar cont de email, fără broker) și, când Render îți cere `TWELVE_DATA_API_KEY`, pune cheia acolo.
4. Click **Apply** / **Deploy**.

**Pas 3 — Așteaptă deploy-ul (~2-3 min prima dată), apoi:**
- Render îți dă un URL de forma `https://market-leadership-dashboard.onrender.com`.
- Deschide URL-ul ăsta direct pe telefon — de oriunde, pe date mobile sau WiFi, fără Mac pornit.
- Salvează-l ca shortcut pe ecranul principal (Share → Add to Home Screen) ca să-l deschizi ca o mini-aplicație.

**De reținut:** planul gratuit Render "adoarme" serviciul după 15 min de inactivitate — prima cerere după o pauză durează ~30-60s până se trezește, apoi merge normal. Nu afectează folosirea zilnică, doar primul refresh după o pauză lungă.

---

## Alternativă — rulare locală pe Mac (dacă preferi, sau pentru testare)

## 1. Cheie Twelve Data (o singură dată, gratuit)

1. Creează un cont gratuit la https://twelvedata.com.
2. Din dashboard-ul Twelve Data, copiază **API key**.
3. Nu publica cheia în GitHub; păstreaz-o doar în `.env` local sau în Render.

## 2. Instalare backend (o singură dată)

```bash
cd market-dashboard/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Deschide `.env` și pune tokenul:
```
TWELVE_DATA_API_KEY=lipeste_aici_cheia_ta
```

## 3. Rulare (pe Mac)

```bash
cd market-dashboard/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` e important — face serverul vizibil și dino rețeaua locală (WiFi),
nu doar de pe Mac. Deschide în browser pe Mac: **http://localhost:8000**

## 4. Acces de pe telefon

### Varianta rapidă — telefonul e pe același WiFi cu Mac-ul
1. Pe Mac, în Terminal, rulează: `ipconfig getifaddr en0` (îți dă IP-ul local, ex `192.168.1.42`).
   Dacă nu merge, încearcă `ipconfig getifaddr en1`, sau System Settings → Wi-Fi → Details.
2. Pe telefon, în browser, deschide: `http://192.168.1.42:8000` (cu IP-ul tău).
3. Dacă nu se încarcă: System Settings → Network → Firewall pe Mac — permite conexiuni
   pentru Python/uvicorn, sau dezactivează temporar firewall-ul cât testezi.

Asta funcționează doar cât Mac-ul e aprins, cu serverul pornit, și telefonul pe același WiFi.

### Varianta pentru acces de oriunde (nu doar acasă)
Dacă vrei să vezi dashboard-ul și pe date mobile / din altă locație, ai nevoie de un tunel:

**Opțiunea simplă — ngrok** (gratuit, temporar, un link nou de fiecare dată):
```bash
brew install ngrok
ngrok http 8000
```
Îți dă un link public `https://xxxx.ngrok-free.app` valid cât ține sesiunea — îl deschizi
de pe telefon de oriunde. La fiecare restart de ngrok, link-ul se schimbă.

**Opțiunea permanentă — Tailscale** (gratuit pentru uz personal, link fix, mai sigur):
Instalezi Tailscale pe Mac și pe telefon, ambele intră într-o rețea privată virtuală,
și accesezi Mac-ul prin IP-ul Tailscale de oriunde ai internet, fără să expui nimic public.
https://tailscale.com/download

Recomand Tailscale dacă vrei să folosești dashboard-ul zilnic de pe telefon, nu doar ocazional.

## Ce faci cu el

- **Confluence Score ≥ 80** → cauți setup activ pe 15M/5M (ICT/SMC) pe
  instrumentul/direcția indicată de bias.
- **60-79** → watchlist, pui alerte, nu deschizi grafic activ.
- **< 60** → ignori, e zgomot.
- **Day Type Predictor** (XAUUSD & US30) → probabilitate relativă de trend day
  vs range day, calculată din Asia range, ADR consumat, ADX zilnic și ziua
  săptămânii.
- **Regime** (Trending / Mean-Reverting / High Vol / Low Vol) acționează ca
  multiplier de încredere pe confluence score.

## Important — de ce unele instrumente sunt proxy

- **Gold vs "DXY"** → nu folosim direct indicele DXY; componenta
  calculează un **USD Basket** direct din cele 7 perechi majore (aceeași
  logică ca USD Strength Score) — conceptual echivalent, doar calculat de noi,
  nu tras de la ICE.
- **Gold vs Real Yields** → folosim `TLT`, un ETF de obligațiuni SUA. Prețul
  obligațiunilor se mișcă în sens invers randamentelor, iar codul ține cont de asta.
- **US30/Nasdaq-100 și mărfuri** → folosim ETF-uri proxy (`DIA`, `QQQ`, `USO`,
  `CPER`), astfel încât dashboard-ul să nu depindă de CFD-urile unui broker.
- **Risk-On/Off** → fără VIX; folosim volatilitatea realizată (ATR%) a proxy-ului US30.
- **Gold Miners (GDX)** a fost eliminat din bonus divergences — înlocuit cu **EURUSD vs GBPUSD** (correlation
  breakdown între cele două perechi, normal corelate direct).

## Structură fișiere

```
backend/
  data.py       -> fetch + cache candele de la Twelve Data API
  scoring.py    -> toate componentele + agregarea în confluence score
  main.py       -> FastAPI, orchestrează tot, serveste și frontend-ul
  .env          -> cheia ta Twelve Data (nu o distribui/nu o pui pe GitHub)
frontend/
  index.html    -> dashboard-ul vizual, responsive (desktop + mobil)
```

## Ajustări

- Ponderile componentelor: `scoring.py`, dict `WEIGHTS` la începutul secțiunii de agregare.
- Praguri entry/watchlist (80/60): `scoring.confluence()`, parametri `entry_threshold` / `watch_threshold`.
- Fereastra de momentum (5 bare zilnice): `main.py`, constanta `MOVE_WINDOW`.
