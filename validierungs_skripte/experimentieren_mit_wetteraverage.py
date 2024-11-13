import pandas as pd
from matplotlib import pyplot as plt

from h2pp import helperFunctions
from h2pp.helperFunctions import resample_time_series_and_extract_values_for_oemof

# todo weitere idee für die Implementierung : nehm nicht nur 2015 sonder mehrere Jahre!!!

unpickled_df = pd.read_pickle("berliner_wetter_df.pkl") # das ist w1[0] gepickled

# rename the 'P' column to 'value' in order to use the typical_day function
df = unpickled_df.rename(columns={'P': 'value'})


ts_resampled_values_summer = helperFunctions.typical_week(df, [6, 7, 8, 9], 0, 60)
ts_resampled_values_winter = helperFunctions.typical_week(df, [12, 1, 2], 0, 60)
ts_resampled_values_transitional = helperFunctions.typical_week(df, [3, 4, 5, 10, 11], 0, 60)


# Hier plotten wir Winter- und Sommeraverage in einem Diagramm
plt.figure(figsize=(12, 6))
num_samples = len(ts_resampled_values_winter)
plt.plot(range(0,num_samples), ts_resampled_values_winter, label='Winter Typical Week', color='blue')
plt.plot(range(0,num_samples), ts_resampled_values_summer, label='Summer Typical Week', color='orange')
plt.plot(range(0,num_samples), ts_resampled_values_transitional, label='Transitional Typical Week', color='green')

plt.xlabel('Hour of the Day')
plt.ylabel('Average Value of P')
plt.title('Typical Week for Winter vs. Summer vs. Transitional Months')
plt.legend()
plt.grid(True)
plt.xticks(range(0, 25))

plt.show()


###### mal für ALLE winter days einzeln Plotten:
# Filter DataFrame for winter months (December, January, February)

df_winter = unpickled_df[(unpickled_df.index.month == 12) | (unpickled_df.index.month == 1) | (unpickled_df.index.month == 2)]

# Create a pivot table to reshape the data for plotting
df_winter['day'] = df_winter.index.date
df_winter['hour'] = df_winter.index.hour

pivot_winter = df_winter.pivot(index='hour', columns='day', values='P')

# Plotting the values
plt.figure(figsize=(12, 6))

for column in pivot_winter.columns:
    plt.plot(pivot_winter.index, pivot_winter[column], alpha=0.5)

plt.xlabel('Hour of the Day')
plt.ylabel('Value of P')
plt.title('Hourly Values of P for All Winter Days')
plt.grid(True)
plt.xticks(range(0, 24))  # Set x-ticks to be every hour

plt.show()
