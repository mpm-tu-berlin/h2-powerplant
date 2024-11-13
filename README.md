# h2-powerplant


This tool aims to assist in the design and integration of hydrogen-based energy storage systems (electrolyzer, fuel cell, hydrogen tank, refuelling station) into micro grids.
It was developed as part of a master's thesis at the Department of Methods of Product Development and Mechatronics at the Technische Universität Berlin. It is developed using Python and largely uses the oemof-solph library for its modelling and optimization processes.

The tool is designed to be flexible so that it can be adapted to different use cases and scenarios (see included examples), but currently focusses mainly on applications in Germany (e.g., due to its consideration of the Energy Market Price composition/properties in Germany).

---

**Copyright Info (Spot Market Prices Germany):** The spot market prices used in the GUI and examples are taken from the data source https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/EEG/Transparenzanforderungen/Marktprämie/Spotmarktpreis-nach-3-Nr-42a-EEG. There, you can select the date range from (here) 01.09.2023 to 31.08.2024 and then download the dataset by clicking "CSV Download", obtaining the same data in the same structure as included in the Examples Folder.

---

## Setup (Tool)


1. Clone the repo locally

2. Setup an environment for the project by installing the packages listed in ```pyproject.toml```:
   - The recommended and most easiest way here is using the poetry package manager. For installing poetry, refer to [this link](https://python-poetry.org/docs/#installing-with-the-official-installer).
   - The suggested Python version is 3.11.*. Python 3.10 also seems to work fine (e.g. if you are using an Ubuntu 22.04 LTS based OS, this Python version comes preinstalled). Python 3.12 should also work. Other versions are not tested yet and therefore not officially supported for now.

#### macOS/Linux
```
poetry env use 3.11
poetry install
```
#### Windows

 If you are using Windows, you have to provide the full path to the desired Python executable, e.g.:
```
 poetry env use C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe
 poetry install
 ```


3. Gather the BDEW data file (see below)

4. Additionally, you will need the following external tools on your system to run the program:
- Solver (see instructions below)
- Graphviz (only for plotting the energy system graph &rarr; see ```ESGraphRenderer``` usages in code), can be downloaded from https://graphviz.org/download/

### Getting BDEW Load Profile Data File
For now, due to open copyright questions, the BDEW load profile data file is not included in this repository
and must be manually downloaded and inserted into the code directory.
You can either
- Manually download the file ```Profile.zip```from the BDEW website (https://www.bdew.de/energie/energieverbraeuche/stromverbrauch-und-erzeugung/lastprofile-strom/), extract the file ```Repräsentative Profile VDEW.xls```, rename it to ```repraesentative_profile_vdew.xls``` and insert it into the ```h2pp/bdew_data``` directory or


- (Recommended) Run the script ```download_bdew.py``` in the project root that automatically downloads the data and inserts it into the right folder ```h2pp/bdew_data``` directory with the right name, also including checking the hash of the downloaded file. Anyways, use the script at your own risk.


### Setting up the Solver
To solve optimization problems, oemof-solph internally uses pyomo which relies on an external solver that needs to be installed on the system.
There are open source as well as proprietary solvers available, with CBC and GLPK being examples for such open source solvers.

The concrete steps may differ from the OS used. For detailed instructions, you might refer
to manuals of OEMOF / Pyomo for further instructions. Some hints follow below. 


#### Windows
You can get the CBC solver binaries from here: https://github.com/coin-or/Cbc/releases (e.g. for a special release, get the Cbc-releases.2.10.11-w64-msvc17-md.zip from https://github.com/coin-or/Cbc/releases/tag/releases%2F2.10.11).
You can copy the cbc.exe from the bin directory to e.g. ```C:\Users\<Your Username>\oemof_solvers``` and insert the path into the PATH variable.

#### macOS
1. Install Homebrew
2. Run ```brew install cbc``` in a terminal window

#### Linux/Ubuntu
Run ```sudo apt-get install  coinor-cbc coinor-libcbc-dev```

For other Linux distributions and/or more information, see https://github.com/coin-or/Cbc.

## Ausführung des Programms


Das Beispiel für ein exemplarisches Industrieareal kann durch Starten der ```Beispielskript.py``` ausgeführt werden. Durch das Studium der dort
enthaltenen Funktionen (sowie der Funktionen, die diese Funktionen wiederrum aufrufen) kann die Funktionsweise des
Programms nachvollzogen werden.

## Aufbau der Ordnerstruktur

Nicht-abschließende Aufzählung, verbleibende Dateien siehe u.a. an gegebener Stelle in den anderen Abschnitten (Setup etc.)

| Ordner/Datei                  | Beschreibung                                                                                                                                                                                                                                                                                          |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```MA_Fallbeispiele```        | Daten und Parameter der Fallbeispiele / Analysen aus der Masterarbeit                                                                                                                                                                                                                                 |
| ```h2pp```                    | Kern des entwickelten Tools (Energiesystemmodellierung, Optimierung, TCO, Technische Machbarkeit) und Definition der Strompreisparameter (ohne Daten der Börsenpreise), BDEW- und PV-Generator                                                                                                        |
| ```gui```                     | Prototyp der Grafischen Oberfläche, Start durch Aufruf der dort enthaltenen Datei ```neue-dash-gui.py```                                                                                                                                                                                              |
| ```validierungs_skripte```    | Kleinere Skripte, mit denen die entwickelten Funktionalitäten überprüft wurden (zu Ansichtszecken, eher Überbleibsel, aber evtl. zur Veranschaulichung sinnvoll)                                                                                                                                      |
| ```config MASTER FILE.json``` | Beispielhafte Konfigurationsdatei, die ALLE möglichen setzbaren Parameter mit Beispielen enhält. Achtung, kann nicht direkt verwendet werden, da sich manche der Parameter gegenseitig ausschließen (bspw. sind Min/Max Leistung für den Elektrolyseur nicht zusammen mit einer fixen Angabe möglich) |
| ```.gitignore```              | Schließt (hier) u.a. den Ordner ```h2pp/bdew_data``` von Git aus, damit die oben heruntergeladene Exceldatei mit den Lastprofilen nicht im Repository inkludiert wird.                                                                                                                                |


## Setup (Fallbeispiele)

In den Fallbeispielen enthalten sind beispielhaft zwei Campi, mit denen das Tool demonstriert wird:
- **EUREF Campus Düsseldorf**: Geplanter Industriepark in Düsseldorf; Angaben u.a. basierend auf öffentlichen Quellen und freien Annahmen
- **Exemplarisches Industrieareal**: Soll exemplarisch Daten des Industrieareals eines Großunternehmens darstellen, um die Integration realer Daten in das Tool zu demonstrieren.

Hierbei wurden aufgrund der geringen Menge belastbarer Daten mehrere Vereinfachungen und Annahmen getroffen, um die Konfigurationsdateien zu erzeugen.
Die genauen Angaben sind den jeweiligen Ordnern und Dateien zu entnehmen. Es folgen noch einige Hinweise zum Aufbau der Fallbeispiele und deren erstmaliger Ausführung.
Hiermit soll auch gezeigt werden, wie eigene Daten im Tool implementiert werden können.

Vorsicht ist geboten, wenn mehrere Skripte parallel ausgeführt werden, da manche Skripte dieselben Dateinamen nutzen, um modifizierte JSON-Dateien o.Ä. zwischenzuspeichern.



### Exemplarisches Industrieareal
Die Daten für das exemplarische Industrieareal sind im Ordner ```MA_Fallbeispiele/Fallstudie Exemplarisches Industrieareal``` enthalten.
Seine Konfiguration findet sich dort in der ```config_microgrid.json```, die auf weitere nötige Dateien für Lastgänge/Zeitreihen verweist. Das Areal nimmt feste Werte für Brennstoffzelle, Elektrolyseur und Tank an.
PV-Leistung und AC-Lastgang werden dabei aus vorhandenen Lastgängen über ein Jahr extrahiert. Der FCEV-Bedarf ist für alle Tage im Jahr gleich und ist eine frei synthetisierte Annahme mit 20 Beispielfahrzeugen, die über den Tag verteilt jeweils vollständig betankt werden.
Der äquivalente EV-Bedarf entspricht dieser Annahme analog und ist auf den entsprechenden äquivalenten Verbrauch von EV (unter Berücksichtigung der höheren Effizienz und längeren Ladedauer) bezogen.

Im Ordner ```Quelldaten und Importerskripte``` finden sich hierzu die Quelldaten (```Lastgänge_und_PV_Leistung.xlsx```), welche mit den in diesem Ordner
ebenfalls enthaltenenen Importerskripten in die für das Tool notwendigen Formate umgewandelt werden können. Die Ergebnisse sind im Ordner ```daten_aufbereitet``` bereits enthalten und werden auch direkt von der ```config_microgrid.json```
verwendet.


### EUREF Düsseldorf
Die Dateien finden sich im Ordner ```MA_Fallbeispiele/Fallstudie EUREF Duesseldorf```.
Dieses Fallbeispiel erstellt generisch Zeitreihen für PV und den Lastgang des Verbrauchs (BDEW). Zur Beschleunigung der Simulation bei mehreren Aufrufen / für die Optimierung und Sensitivitätsanalysen
werden hierbei aber zunächst die PV- und BDEW-Zeitreihen vorab berechnet und in CSV-Dateien extrahiert. 

**Hierzu müssen zunächst Skripte ausgeführt werden, um diese aufbereiteten Zeitreihen sowie eine JSON-Konfigurationsdatei, welche
mit diesen aufbereiteten Zeitreihen arbeitet, zu erstellen,** ansonsten können die gegebenen Fallbeispiele nicht ausgeführt werden:

1. Ausführen von ```MA_Fallbeispiele/Common_Data/bev_fcev_without_weekends/generate.py```: Dies erstellt nicht nur basierend auf den Dateien ```ev_equiv_dummy_time_series.csv``` und ```ev_equiv_dummy_time_series.csv``` im Ordner ```MA_Fallbeispiele/Common_Data```eine Variation der Zeitreihen für die Bedarfe für die FCEV/EV Fahrzeugflotte, welche
statt täglich, nur Mo-Fr einen Bedarf haben (im Einklang mit dem angenommenen Lastprofil G1 für diesen Campus), sondern auch für die Variation des FCEV Bedarfs in der Sensitivitätsanalyse (Streckung/Stauchung).


2. Ausführen von  ```MA_Fallbeispiele/Fallstudie EUREF Duesseldorf/pre_calculated_content/Generator Script.py```, um PV- und BDEW-Zeitreihen vorab für die schnelle Evaluierung zu generieren und in CSV-Dateien im richtigen Format abzuspeichern.
Hierdurch wird eine Datei ```__output_precalculated_pv_and_bdew_config_euref_dus.json``` im selben Verzeichnis erzeugt.

3. Diese Datei ist umzubenennen und dann in den Ordner ```MA_Fallbeispiele/Fallstudie EUREF Duesseldorf/generated_ts_config_euref_dus.json``` zu kopieren/verschieben (Hierbei vorsichtig sein oder am besten mit einem Dateiexplorer der Wahl durchführen, um ein Refactoring durch die IDE oder ein Hinzufügen zu Git zu vermeiden).

Die grundlegenden Parameter des Areals, die dem Schritt 2 oben zugrunde liegen, finden sich hierbei im Unterordner des Fallbeispiels in der Datei ```pre_calculated_content/input_dus.json``` und spezifizieren Parameter für die manuelle PV- und BDEW-Kalkulation.
Die Datei kann an sich direkt für die Simulation genutzt werden (keine expliziten Fallbeispiele hierfür enthalten) sofern oben die Dateien für EV/FCEV erzeugt wurden oder es wird durch Ausführen von Schritt 2 und folgende oben entsprechende Datei erzeugt und mit den Fallbeispielen verwendet.

**Sollen Anpassungen an den Werten vorgenommen werden, so sollte zunächst die ```input_dus.json``` modifiziert werden und anschließend erneut die weiteren oben genannten Schritte ausgeführt werden!**

**Kann die Datei des Fallbeispiels ```MA_Fallbeispiele/03_A_EUREF_Duesseldorf.py``` anschließend korrekt (ohne Fehler, d.h. ```Process finished with exit code 0```) ausgeführt werden, kann davon ausgegangen werden, dass alle Konfigurationsschritte (inkl. Installation Dependencies, Einrichtung Solver, BDEW-Datei etc.) erfolgreich waren.**

## "Frequently" Asked Questions

### FAQ - Tool
1. I get ```invalid value encountered in scalar divide``` error in the console output when running sth. in the GUI. What should I do? &rarr; Check if you have specified an electric consumption for the grid. A consumption of exactly 0 leads to division by zero errors at multiple places in the code. If you want to model a grid without electrical demand, set the demand to a very small value (e.g. 1 kWh) instead.


### FAQ - Development
1. I get "index out of range" when running the OEMOF optimization after I added new components ord did changes &rarr; 
are all time series or variable_costs in the flows passed in the correct format and length? oemof does not give an explicit error message if not.

2. I get the following Error that not directly points to a cause:
```
KeyError: 'Index \'("<oemof.solph.components._source.Source: \'s_h2_grid\'>", "<oemof.solph.buses._bus.Bus: \'h2_700bar\'>", 0, 0)\' is not valid for indexed component \'flow\''
```
&rarr; Check if all components are added to the Energy System!

3. I get the error:
```
ValueError: No value for uninitialized NumericValue object flow[h2_700bar,Brennstoffzelle,0,0]
```
&rarr; The model might probably be infeasible (unlösbar) in this case! If you scroll a bit up in the console output,
you can probably read the message (in the normal console output color)

```
WARNING: Loading a SolverResults object with a warning status into
model.name="Model";
    - termination condition: infeasible
```

&rarr; Solution: Especially check if really everything is possible. For example, imagine not having a hydrogen market
and no tank but a demand that is bigger than your electrolyzer, so that the model cannot be solved.

4. I get the error:

```
ValueError: Length mismatch: Expected axis has 2 elements, new values have 98 elements
```
&rarr; similar to error 3. For example, this could happen if power prices for buying are (for some reason)
so low that a direct selling after buying is more profitable (absoulute selling price higher than buying price),
leading to infeasibility.


## Good to know

- Bei den Eingabedateien beziehen sich alle Energieangaben auf kWh bzw. Leistungsangaben beziehen sich auf kW, auch die angegebene Energiemenge des Wasserstoffs bei den CSV-Dateien für Lastgänge ist normiert in kWh angegeben
und wird dann intern kg umgerechnet für Plots/Preisberechnung/Outputs.


- The script for plotting the energy system graph is based on oemof-visio (https://github.com/oemof/oemof-visio/blob/09fca323ff72ccc358e23b1efe1c8e61ce2f1bd0/oemof_visio/energy_system_graph.py),
manually modified to work with the current version of oemof.solph.


- Zum Export der Plotly-Grafiken als PDF wird Kaleido benötigt, dies ist den Dependencies bereits hinzugefügt und im Code umgesetzt. Siehe https://plotly.com/python/static-image-export/


- **Custom CSS auf der GUI**: Gemäß https://dash.plotly.com/external-resources, im ```assets``` Ordner abgelegt


- **Anwendbarkeit alter oemof Tutorials**: In den neuen OEMOF Versionen gibt es einige Renames, die in alten (tlw. "aktuellen") Tutorials verwendet werden, aber mittlerweile
entweder nicht funktionieren oder zumindest deprecated sind:
  - Transformer -> heißt jetzt Converter
  - Component -> ist jetzt ein Node


