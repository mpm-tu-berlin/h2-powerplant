import pandas as pd
from matplotlib import pyplot as plt

from h2pp import helperFunctions

# todo die Jahre..

# Datenquelle für Export: https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/EEG/Transparenzanforderungen/Marktprämie/Spotmarktpreis-nach-3-Nr-42a-EEG
# Spotmarktpreis 2024 DEU: https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/EEG/Transparenzanforderungen/Marktprämie/Spotmarktpreis-nach-3-Nr-42a-EEG

file_path = '../MA_Fallbeispiele/Common_Data/Spotmarktpreis DEU 2023-09 bis 2024-08.csv'
df_final = helperFunctions.netztransparenz_importer(file_path)

# todo samstag und sonntag separat betrachtet?
ts_resampled_values_winter = helperFunctions.typical_week(df_final, [12, 1, 2], 0, 60)

# Display the result
#print(typical_day_winter)

ts_resampled_values_summer = helperFunctions.typical_week(df_final, [6, 7, 8, 9], 0, 60)

# Übergangszeit

ts_resampled_values_transitional = helperFunctions.typical_week(df_final, [3, 4, 5, 10, 11], 0, 60)


# Hier plotten wir Winter- und Sommeraverage in einem Diagramm
plt.figure(figsize=(12, 6))

num_samples = len(ts_resampled_values_winter)
plt.plot(range(0,num_samples), ts_resampled_values_winter, label='Typische Winterwoche', color='blue')
plt.plot(range(0,num_samples), ts_resampled_values_summer, label='Typische Sommerwoche', color='orange')
plt.plot(range(0,num_samples), ts_resampled_values_transitional, label='Typische Übergangswoche', color='green')

plt.xlabel('Stunden seit Montag 0:00')
plt.ylabel('Durchschnittliche Kosten EUR/kWh')
plt.title('Spotmarktpreis - Typische Woche für Winter / Sommer / Übergangsmonat')
plt.legend()
plt.grid(True)
#plt.xlabel(range(0, 25))

plt.show()