import os

import pandas as pd

# Load the Excel file and specify the sheet and header row
file_path = 'Lastgänge_und_PV_Leistung.xlsx'
sheet_name = 'Tabelle'
header_row = 2  # Since Python is 0-indexed, A3 corresponds to row index 2

# Read the data from the specified sheet and header row
df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)

# Convert 'Zeitraum' to the start datetime only
df['datetime'] = pd.to_datetime(df['Zeitraum'].str.split('-').str[0].str.strip(), format='%d.%m.%Y %H:%M')

#todo timezone hinzufügen nötig? (+0000 wie bei den andern Files usw)

# Gather 'Zähler 1' and 'Zähler 2' and sum them up
df['value'] = df['Hauptzähler_1'] + df['Hauptzähler_2']

# Select the required columns
result_df = df[['datetime', 'value']]

# Define the output path
output_dir = os.path.join('..', 'daten_aufbereitet')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'verbraeuche_microgrid_pv_einbrueche.csv')

# Save the result to a CSV file
result_df.to_csv(output_path,index=False)