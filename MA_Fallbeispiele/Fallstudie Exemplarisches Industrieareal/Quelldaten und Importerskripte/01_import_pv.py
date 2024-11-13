import pandas as pd
import os

# Load the Excel file and specify the sheet and header row
file_path = 'Lastgänge_und_PV_Leistung.xlsx'
sheet_name = 'PV_Daten'
header_row = 0  # Since Python is 0-indexed, A1 corresponds to row index 0

# Read the data from the specified sheet and header row; skip the empty line after header
df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row, skiprows=[1])

# Convert 'Datumzzz' to datetime format and set timezone to UTC+0
df['datetime'] = pd.to_datetime(df['Datenpunktadresse'], format='%d.%m.%Y %H:%M')

#todo timezone hinzufügen nötig? (+0000 wie bei den andern Files usw)


# Calculate the sum of the values in columns B to F, handling NaN values correctly
df['value'] = df.iloc[:, 1:6].sum(axis=1, skipna=True)

# Select the required columns
result_df = df[['datetime', 'value']]

# Define the output path
output_dir = os.path.join('..', 'daten_aufbereitet')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'pv_microgrid.csv')

# Save the result to a CSV file
result_df.to_csv(output_path, index=False)
