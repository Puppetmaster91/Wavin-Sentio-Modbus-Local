# Wavin Sentio (lokal Modbus) til Home Assistant

[English](README.md) · **Dansk**

Lokal integration uden cloud til **Wavin Sentio** centralenhed (CCU-208) via **Modbus TCP**.
Opsættes i brugerfladen, ingen YAML nødvendig.

> ## ⚠️ Læs det her først: AI-skrevet software
>
> Integrationen er **skrevet af en AI-assistent (Claude fra Anthropic)** i en samtale med
> repoets ejer, der styrede arbejdet og testede det på sin egen installation. Den er **ikke**
> skrevet eller gennemgået af en professionel udvikler eller af Wavin.
>
> - **Den kan indeholde fejl og forkerte antagelser.** Registrenes betydning stammer fra
>   Wavins offentlige Modbus-manual, ikke fra Wavins kildekode.
> - Den er testet på **én rigtig installation** (se [Testet opsætning](#testet-opsætning)) og
>   ellers kun mod en simulator. Din opsætning kan opføre sig anderledes.
> - Dele af Home Assistant-siden er aldrig kørt i et CI-miljø. Forvent skarpe kanter.
> - **Integrationen kan skrive til din varmestyring** (setpunkter, modes, standby, ferie).
>   Forkerte værdier kan påvirke komfort og energiforbrug. Start med controlleren i
>   *Read only*, hvis du er i tvivl.
> - Leveres "som den er" under MIT-licensen, **uden nogen garanti**. Stol ikke på den til noget
>   sikkerhedskritisk (frostsikring, oversvømmelse osv.). Controllerens egne sikkerhedsfunktioner
>   kører uafhængigt af Home Assistant.
> - **Uofficiel.** Ikke tilknyttet, godkendt eller supporteret af Wavin eller Orbia. Kontakt
>   ikke Wavins support om problemer med integrationen.
>
> Fejlrapporter og pull requests er meget velkomne, se [Bidrag](#bidrag).

## Indhold

- [Funktioner](#funktioner)
- [Testet opsætning](#testet-opsætning)
- [Krav](#krav)
- [Aktivér Modbus TCP på Sentio](#aktivér-modbus-tcp-på-sentio)
- [Installation](#installation)
- [Opsætning](#opsætning)
- [Devices og entities](#devices-og-entities)
- [Brug af integrationen](#brug-af-integrationen)
- [Indstillinger](#indstillinger)
- [Fjern ubrugte devices](#fjern-ubrugte-devices)
- [Læs rå registre (debug-handling)](#læs-rå-registre-debug-handling)
- [Fejlfinding](#fejlfinding)
- [Begrænsninger](#begrænsninger)
- [Sikkerhed](#sikkerhed)
- [Bidrag](#bidrag)
- [Hvordan den blev lavet](#hvordan-den-blev-lavet)
- [Licens](#licens)

## Funktioner

- Helt **lokal** via Modbus TCP (port 502). Ingen Wavin-konto og ingen internetadgang nødvendig.
- Devices opbygget som din installation:
  - ét device til **controlleren** (`Wavin Sentio CCU#xxxx`),
  - ét device **pr. zone** (navnet læses fra zonen i Sentio),
  - ét device pr. **varmekreds (HCC)** i brug,
  - ét device til **varmekilden** (fyr / varmepumpe).
- Zoner, kredse og varmekilde **findes automatisk**. Ubrugte oprettes ikke som standard og kan
  slås til og fra i indstillingerne.
- **Climate-entity pr. zone** med aktuel temperatur, måltemperatur og Tidsplan/Manuel-mode.
- Termistorindgange **T1–T5**, udetemperatur og en **ΔT-sensor** (fremløb/retur).
- Pumpestatus, fremløbstemperatur, fyrets tilstand og fejlflag.
- Læsninger samles, "optaget"-svar prøves igen, og ugyldige værdier vises som
  *utilgængelig* i stedet for mærkelige tal.
- En debug-handling til at læse rå registre, nyttig i fejlrapporter.
- Engelske og danske oversættelser.

## Testet opsætning

Forfatterens installation som reference:

- Sentio CCU-208, firmware **TM60018.4**, Modbus TCP sat til *Slave Read/write*
- 8 zoner (to zoner deler én rumføler, to zoner ubrugte), ingen gulvfølere
- Gasfyr med 3-vejsventil og varmeveksler til gulvvarmen
- Gulvvarmekreds med egen pumpe på udgang P1 (ses af integrationen som **HCC1**)
- Fremløbsføler på **T2**, returføler på **T3**
- Home Assistant OS

Alt andet i Wavins manual (ITC-controllere, brugsvand, buffertank, ventilation, affugtere,
køling) er **ikke testet** og for det meste ikke implementeret, se
[Begrænsninger](#begrænsninger).

## Krav

- Sentio-firmware **TM60014 eller nyere** (kræves til Modbus TCP ifølge Wavins manual).
- Modbus TCP aktiveret på controlleren, se nedenfor.
- Controlleren skal kunne nås på dit netværk. Brug en **fast IP** (DHCP-reservation i routeren).
- Home Assistant **2025.3 eller nyere**. Minimumskravet er et skøn og er ikke verificeret mod
  ældre versioner.
- Valgfrit: [HACS](https://hacs.xyz/) til installation og opdateringer.

## Aktivér Modbus TCP på Sentio

Modbus er **slået fra som standard**. På Sentio-displayet:

1. Gå til **System → Installer settings → Modbus settings → Modbus TCP**.
2. Vælg en mode:
   - **Read only**: kun overvågning. Skrivninger fra Home Assistant afvises.
   - **Read/write**: kræves for at ændre setpunkter, modes, standby og ferie.
   - *Write with password* understøttes **ikke** af integrationen (den sender aldrig
     adgangskoden), så skrivning fejler i den mode.
3. Notér controllerens IP-adresse (eller reservér en i routeren). DHCP-hostname er
   `Wavin Sentio CCU#` efterfulgt af de sidste fire cifre i serienummeret.

## Installation

### HACS (custom repository)

1. Åbn **HACS** i Home Assistant, derefter menuen (⋮) → **Custom repositories**.
2. Tilføj `https://github.com/puppetmaster91/Wavin-Sentio-Modbus-Local` med kategori **Integration**.
3. Find **Wavin Sentio** i HACS, installér den, og **genstart Home Assistant**.

### Manuelt

1. Download dette repo.
2. Kopiér mappen `custom_components/wavin_sentio` til `/config/custom_components/` på din
   Home Assistant (så du får `/config/custom_components/wavin_sentio/`).
3. Genstart Home Assistant.

## Opsætning

1. **Indstillinger → Enheder og tjenester → Tilføj integration**, søg efter **Wavin Sentio**.
2. Indtast:
   - **IP-adresse** på controlleren,
   - **Port**: `502`,
   - **Modbus unit ID**: `1` (manualen nævner også `255` "hvis nødvendigt", så prøv den, hvis
     `1` ikke svarer).
3. Integrationen læser controllerens serienummer, finder zoner og kredse og opretter devices.
   Titlen bliver `Wavin Sentio CCU#xxxx`.

Der tillades kun én entry pr. controller. Ændres IP-adressen, opdaterer en ny tilføjelse af
samme controller den gemte adresse.

## Devices og entities

Entity-id'er dannes af device- og entity-navn, så dine afviger fra eksemplerne. Entities
markeret *diagnostik* skjules på standardkort. Entities markeret *slået fra som standard*
oprettes deaktiveret og kan aktiveres i entity-indstillingerne.

### Controller: `Wavin Sentio CCU#xxxx`

| Entity | Type | Bemærkning |
|---|---|---|
| Standby | switch | Standby for hele anlægget. Skriver til Standby-registeret. |
| Ferie | switch | Ferie-mode for hele anlægget. |
| Udetemperatur | sensor | Fra Sentios udeføler-indgang. |
| Varme/køl-mode | sensor | `heating` eller `cooling`. |
| Termistorindgang T1–T5 | sensor | Rå temperaturer. Kun indgange med tilsluttet føler er aktive som standard. Omdøb dem (fx T2 → "Fremløb"). |
| Forskel fremløb/retur | sensor | ΔT i K. Standard er **T2 minus T3**. Vælg andre indgange i indstillingerne. |
| Advarsel / Fejl | binary sensor, diagnostik | Samlede flag for hele systemet. |

### Zone-devices (ét pr. zone)

| Entity | Type | Bemærkning |
|---|---|---|
| *(zonenavn)* | climate | Se [Climate](#climate). |
| Lufttemperatur | sensor | Aktiv som standard kun hvis zonen rapporterer en værdi. |
| Luftfugtighed | sensor | Samme. |
| Gulvtemperatur | sensor | Samme. Ikke aktiv, hvis du ingen gulvføler har. |
| Dugpunkt | sensor, diagnostik | |
| Ønsket temperatur | sensor, diagnostik, slået fra som standard | Controllerens effektive mål. |
| Tilstand | sensor, diagnostik | `idle`, `heating`, `cooling`, `blocked_heating`, `blocked_cooling`. |
| Blokeringsårsag | sensor, diagnostik | Hvorfor zonen er blokeret, fx `contact`, `outdoor_temp`, `deadband`. |
| Advarsel, Fejl, Lavt batteri, Føler mistet | binary sensor, diagnostik | |

Zoner, der deler rumføler (fx to zoner i samme rum), får hver deres device. En zone uden egen
føler kan have *utilgængelig* lufttemperatur og luftfugtighed. Har to zoner samme navn,
tilføjes zonenummeret til device-navnet.

### Varmekreds-devices (HCC1–HCC3, kun dem i brug)

| Entity | Type | Bemærkning |
|---|---|---|
| Pumpe | binary sensor (kører) | Pumpestatus som rapporteret af controlleren. |
| Pumpe efterspurgt | binary sensor, diagnostik | |
| Fremløbstemperatur | sensor | Målt fremløbstemperatur for kredsen. |
| Ønsket fremløbstemperatur | sensor | Controllerens beregnede mål (varmekurve). |
| Højeste ønskede rumtemperatur | sensor, diagnostik | Aktiv kun hvis den rapporteres. |
| Tilstand, Blokeringsårsag | sensor, diagnostik | |
| Advarsel, Fejl, Fremløbsføler fejl, Høj temperatur afbrydelse | binary sensor, diagnostik | |

Wavins manual har **ingen registre til de fysiske pumpeudgange (P1/P2)**. Pumpestatus hentes
fra den varmekreds, pumpen hører til.

### Varmekilde-device

Oprettes, når controlleren rapporterer en H/C source eller et fyr/en varmepumpe.

| Entity | Type | Bemærkning |
|---|---|---|
| Tilstand (H/C source) | sensor | |
| Fyr tilstand | sensor | `idle`, `heating_active`, `blocked_heating`, `failure` osv. |
| Ønsket fyrtemperatur | sensor | |
| Fyr indløbstemperatur | sensor | Aktiv kun hvis en føler rapporterer en værdi. |
| Blokeringsårsag | sensor, diagnostik | |
| Advarsel / Fejl / generel fejl | binary sensor, diagnostik | Flag, firmwaren ikke leverer, vises som *ukendt*. |

## Brug af integrationen

### Climate

Hver zone har en climate-entity.

- **HVAC-modes:** `Heat` = **Manuel** mode i Sentio, `Auto` = **Tidsplan**.
- **Aktuel temperatur:** zonens lufttemperatur.
- **Måltemperatur:** controllerens **effektive** ønskede temperatur. Den følger tidsplan, ferie,
  standby eller midlertidig override og kan derfor ændre sig af sig selv.
- **Sætter du en temperatur** fra Home Assistant, skrives det manuelle setpunkt **og zonen
  skiftes til Manuel (Heat)**, fordi Sentio ignorerer det manuelle setpunkt i tidsplan-mode.
  Skift zonen tilbage til **Auto** for at vende tilbage til tidsplanen.
- **Trin** er 0,5 °C, område 5–35 °C. Controlleren kan afrunde eller begrænse efter egne trin
  og grænser.
- **Attributter:** `manual_setpoint`, `override` (`none`, `temporary`, `vacation_away`,
  `adjust`), `blocking_source` og `zone`.
- Handlingen er `heating` / `cooling` / `idle` ud fra zonens tilstand.

### Standby og ferie

De to switches på controller-devicet slår hele anlæggets Standby- eller Ferie-mode til og fra.

### Eksempel: besked ved controller-fejl

```yaml
automation:
  - alias: "Wavin Sentio fejl"
    triggers:
      - trigger: state
        entity_id: binary_sensor.wavin_sentio_ccu_1234_error   # tilpas til din entity
        to: "on"
    actions:
      - action: notify.notify
        data:
          message: "Wavin Sentio rapporterer en fejl."
```

### Eksempel: fremløb, retur og ΔT på et dashboard

Tilføj de tre sensorer (T2 og T3, omdøbt, samt *Forskel fremløb/retur*) til et entities-kort
eller en historikgraf.

## Indstillinger

Åbn integrationen og tryk på tandhjulet (**Konfigurer**).

| Indstilling | Beskrivelse |
|---|---|
| Zoner der oprettes | Vælg, hvilke af de fundne zoner der bliver til devices. |
| Varmekredse (HCC) der oprettes | Vises kun, hvis kredse blev fundet. |
| Fremløbs- / returtermistor til ΔT | Vælg T1–T5, eller `-` for at slå ΔT-sensoren fra. |
| Opdateringsinterval | 5–300 sekunder. Standard 15. Hver opdatering laver cirka 30 Modbus-kald med en typisk opsætning. |

Integrationen genindlæses, når du gemmer. **Opdagelse sker, når integrationen indlæses.**
Tilslutter du en ny zone eller kreds senere, så genindlæs integrationen (⋮ → **Genindlæs**),
så den bliver fundet, og vælg den derefter i indstillingerne.

Som standard oprettes en zone kun, hvis den rapporterer en gyldig ønsket temperatur, og en
kreds kun, hvis den rapporterer en gyldig fremløbstemperatur. Sådan holdes ubrugte zoner og
kredse ude.

## Fjern ubrugte devices

Devices for zoner eller kredse, du har fravalgt, kan slettes: åbn devicet → ⋮ →
**Slet enhed**. Controller-devicet og alle aktive devices er beskyttet og kan ikke slettes.
Ser du kun *Deaktiver*, er devicet stadig valgt i indstillingerne.

## Læs rå registre (debug-handling)

Handlingen `wavin_sentio.read_registers` læser rå Modbus-registre og returnerer dem. Den er til
fejlsøgning, til at udforske en opsætning og til fejlrapporter. Den skriver aldrig.

Åbn **Udviklerværktøjer → Handlinger**, skift til YAML-tilstand og kør fx:

```yaml
action: wavin_sentio.read_registers
data:
  type: input        # input | holding | discrete
  address: 7701      # registernummer præcis som i Wavins manual
  count: 8
  individually: true # læs ét ad gangen, så manglende registre ikke afbryder hele læsningen
```

Svaret indeholder `raw`-værdier, og for 16-bit registre også `fp100` (værdien divideret med 100,
`null` for den ugyldige markør `0x7FFF`). Manglende registre vises som `error: exception 2`
("illegal data address"), hvilket blot betyder, at registeret ikke findes på din opsætning.

Registernumre bruges **præcis som i manualen** (ingen ±1-forskydning).

## Fejlfinding

Slå debug-logning til, og vedlæg loggen i fejlrapporter:

```yaml
logger:
  default: warning
  logs:
    custom_components.wavin_sentio: debug
```

| Problem | Prøv |
|---|---|
| "Kan ikke forbinde" under opsætning | Tjek IP, at Modbus TCP er aktiveret på displayet, at firmwaren er TM60014 eller nyere, og at port 502 ikke er blokeret. Er en anden Modbus-klient (Node-RED o.l.) forbundet, så prøv at lukke den. Det sidste er et forslag og ikke verificeret. |
| "Controlleren svarede med en Modbus-fejl" | Prøv unit ID `255` i stedet for `1`. |
| Skrivning fejler eller har ingen effekt | Modbus-mode skal være *Read/write* (ikke *Read only* eller *Write with password*). |
| Måltemperaturen bliver ikke stående | I tidsplan-mode vinder tidsplanen. Sætter du en temperatur fra Home Assistant, skiftes zonen til Manuel, tjek at det skete. |
| Entities er *utilgængelige* | Controlleren returnerede den ugyldige markør `0x7FFF`: ingen føler tilsluttet, eller en trådløs føler har ikke rapporteret endnu. For zoner der deler en føler, rapporterer måske kun den zone, der ejer den. |
| Zone eller kreds mangler | Den rapporterer ingen gyldig værdi og er derfor ikke valgt som standard. Vælg den i indstillingerne. For noget nyligt tilsluttet: genindlæs integrationen først. |
| Enkelte korte fejl eller huller | Controlleren svarer "optaget" under opstart og mens den gemmer sin konfiguration. Integrationen prøver automatisk igen. |
| Værdier ser forkerte ud, eller et register er ikke, som du forventer | Brug debug-handlingen og opret en issue. Firmwareversioner afviger, og Wavin skriver, at registerlisten ikke er endelig. |
| Entity-id'er er ikke som forventet | Id'er dannes af device- og entity-navne ved første oprettelse. Omdøb entities i brugerfladen. De beholder et stabilt unikt id. |

## Begrænsninger

- **Ikke implementeret:** ITC-controllere (73xx/74xx), brugsvand (Calefa DHW-201 og tank),
  buffertank-styring, ventilation, affugtere, perifer-listen (termostater og følere med
  signalstyrke), skrivning af navne, tidsplaner, tuning-parametre (varmekurve og lignende),
  overstyring af udetemperatur og Modbus *Write with password*.
- Registrene findes i Wavins manual, så det kan tilføjes. Registerudtræk fra installationer, der
  har dem, hjælper meget.
- **Køling** er kun delvist håndteret. Modet vises, og climate-handlingen kan rapportere
  `cooling`, men ingen har testet det. Climate-entiteten tilbyder kun Heat og Auto.
- **Dummy-rum** (zoner uden termostat eller føler) springes over.
- Én controller pr. config entry. Flere controllere kan hver tilføjes.
- Opdatering sker ved polling. Controlleren sender ikke selv data.
- Wavins manual skriver, at Modbus-interfacet **ikke** er tænkt som bruger- eller
  installatørinterface, men til overvågning, tuning og begrænsning af brugere.
- Modbus på Sentio understøtter højst 32 registre pr. læsning. Integrationen holder sig inden for det.

## Sikkerhed

- **Modbus TCP har ingen autentificering eller kryptering.** Alle, der kan nå port 502, kan læse
  og i *Read/write*-mode ændre værdier uden om Home Assistant. Hold controlleren på et
  betroet netværk eller VLAN, og åbn aldrig port 502 mod internettet.
- Foretræk *Read only*, hvis du kun vil overvåge.
- Ændring af setpunkter og modes påvirker din varme og dit energiforbrug. Brug automationer, der
  skriver til Sentio, med omtanke, og undgå meget hyppige skrivninger: efter ændringer kører
  controlleren en konfigurationsgemning og kan svare "optaget" imens.
- Frostsikring, højtemperaturafbrydelse og andre sikkerhedsfunktioner kører inde i Sentio.
  Slå dem ikke fra med noget værktøj.

## Bidrag

Fejlrapporter, registerudtræk og pull requests er velkomne.

Ved oprettelse af en issue, vedlæg gerne:

- Sentio-firmwareversion (Systeminformation på displayet) og controllermodel
- Hvilken hardware der er tilsluttet (gulvvarme, radiatorer, fyr eller varmepumpe, brugsvand, ventilation)
- Home Assistant-version og integrationsversion
- Debug-logs fra `custom_components.wavin_sentio`
- Hvis relevant, output fra `wavin_sentio.read_registers` for de pågældende registre

Nyttige registerområder at udtrække fra opsætninger, der har dem (brug `individually: true`):

| Hvad | Type | Start | Antal |
|---|---|---|---|
| ITC1 | input / discrete | 7301 / 7301 | 10 / 8 |
| HCC1–HCC3 | input | 7701, 7801, 7901 | 8 |
| H/C source | input | 8101 | 1 |
| Fyr / varmepumpe | input | 8201 | 4 |
| Buffertank | input | 8301 | 5 |
| Brugsvand (DHW-201) | input | 6501 | 12 |
| Brugsvandstank | input | 6601 | 8 |
| Ventilation 1 | input | 61001 | 38 |
| Affugter 1 | input | 65001 | 12 |

Læs ændringer i koden grundigt: projektet har ingen automatiske tests mod rigtig hardware, så
gennemgang af mennesker, der kender Sentio, er værdifuld.

## Hvordan den blev lavet

- Skrevet af **Claude (Anthropic)** ud fra Wavins offentlige *Sentio Modbus Manual* (august 2024,
  firmwarepakke 3.2–3.4) og en forumtråd i fællesskabet om Sentio på Modbus TCP, styret af
  repoets ejer.
- Modbus-laget er en lille asyncio-klient uden afhængigheder (`api.py`), så den ikke afhænger af
  den `pymodbus`-version, din Home Assistant har.
- Registerlogikken blev testet mod en simuleret Sentio, inklusive "optaget"-svar, manglende
  registre, ugyldige værdier, skrivninger og forfatterens rigtige registerværdier.
  Home Assistant-koden (entities, config flow) blev syntakstjekket og derefter brugt på
  forfatterens rigtige installation, men har ingen automatisk testsuite.
- Behandl koden som al anden ugennemgået kode fra tredjepart.

## Licens

[MIT](LICENSE). Wavin og Sentio er varemærker tilhørende deres respektive ejere og bruges her
kun til at beskrive kompatibilitet.
