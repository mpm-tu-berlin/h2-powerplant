# Einfaches Skript das den Gesamt-Jahresbedarf aus der
# "../daten_aufbereitet/verbraeuche_microgrid_rekonstruiert.csv" berechnet
import pandas as pd
import h2pp
from h2pp.generators import Jahreszeit, typical_months

df = pd.read_csv("../daten_aufbereitet/verbraeuche_microgrid_rekonstruiert.csv", parse_dates=True, index_col='datetime')
# Mittelungs funktion, fuer die Jahreszeiten

### Gesamt Gemittelt
total = 0
for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
    #df.loc[df['Jahreszeit'] == jahreszeit.value, 'Jahreszeit'] = jahreszeit.name
    mo = typical_months(jahreszeit)
    tw = h2pp.helperFunctions.typical_week(df, mo, 2, 15)

    # Letztes Intervall rauswerfen
    tw = tw[:-1]
    # Gesamtenergie ermitteln
    gesamt_woche = tw.sum() * (15 / 60)

    num_weeks = h2pp.helperFunctions.sum_days_in_months(mo) / 7
    total += gesamt_woche * num_weeks

print(total)

### Testweise nochmal mit dem gesamten Dataframe.
sum_year_ohne_rundung = df['value'].sum() * (15 / 60)
print(sum_year_ohne_rundung)