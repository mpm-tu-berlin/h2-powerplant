# Combine "pv_microgrid.csv" and "verbraeuche_microgrid_pv_einbrueche.csv" into a single DataFrame

import pandas as pd
import os

# Load the two CSV files
the_path = os.path.join('..', 'daten_aufbereitet')
pv_file_path = os.path.join(the_path, 'pv_microgrid.csv')
consumption_file_path = os.path.join(the_path, 'verbraeuche_microgrid_pv_einbrueche.csv')

pv_df = pd.read_csv(pv_file_path)
consumption_df = pd.read_csv(consumption_file_path)

# Merge the two DataFrames on the 'datetime' column
result_df = pd.merge(pv_df, consumption_df, on='datetime', how='outer', suffixes=('_pv', '_consumption'))

# Beide addieren
result_df['value'] = result_df['value_pv'] + result_df['value_consumption']

# datetime,value in CSV speichern
output_path = os.path.join(the_path, 'verbraeuche_microgrid_rekonstruiert.csv')
result_df[['datetime', 'value']].to_csv(output_path, index=False)
print("ok")