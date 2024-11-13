import os

import pandas as pd
import oemof.solph as solph

from h2pp.oemof_visio_energy_system_graph import ESGraphRenderer


import matplotlib.pyplot as plt

### Expected cost (by using the file einfacher_verbraucher_50_impuls.csv) for the compressor:
### we have 7x 50kW peaks, so 350kW in total. The compressor has a needed compression energy of 5.122, so (350kW / (33.33 kg / kWh)) * 5.122 kWh/kg  = 53.78 kWh Power
# 53.78 kWh * 0.3 EUR/kWh = 16.13 EUR
# H2 cost: 7x 50 kW = 350 kW; with 33.33 kWh/kg H2, this is 10.5 kg H2. At 9.5 EUR/kg, this is 99.75 EUR
# This makes a total of 115.88 EUR

def plot_data(data1, data2, data3, legend_names):
    fig, ax = plt.subplots()

    # Farben für die Graphen
    colors = ['r', 'g', 'b']

    # x-Achsen Labels
    x_labels = [f"{i:02d}:00" for i in range(25)]

    # y-Achsen Werte
    y_values = []
    for data in [data1, data2, data3]:
        sequence = data["sequences"].values[:25, 0]
        print("Peak value of sequence: ", max(sequence))
        print("Sum of power: ", sum(sequence))
        y_values.append(sequence)

    # Plotten der Daten
    for i, y in enumerate(y_values):
        ax.plot(x_labels, y, color=colors[i])

    # Achsenbeschriftungen
    ax.set_xlabel('Uhrzeit')
    ax.set_ylabel('Power values')

    # Titel
    ax.set_title('Power values über die Zeit')

    # x-Achsen Ticks
    ax.set_xticks(range(0, 26, 2))
    ax.set_xticklabels(x_labels[::2], rotation=45)

    # Gitter anzeigen
    ax.grid(True)

    # Legende
    ax.legend(legend_names)

    # Anpassen des Layouts
    plt.tight_layout()

    # Plot anzeigen
    plt.show()

import h2pp.generators
from h2pp.generators import (create_electrolyzer, create_fuel_cell_chp,
                             create_h2_storage, convert_kWh_to_kg_H2, convert_kg_H2_to_kWh, create_compressor_a,
                             import_and_normalize_one_day_time_series_csv, create_const_time_series, create_simple_inverter)
import matplotlib.pyplot as plt

freq_in_min = 60
my_index = pd.date_range(start='2020-01-01',
                             end='2020-01-02',
                             inclusive='both',  # rechtsoffenes intervall
                             freq=f"{freq_in_min}min")

# Nutze diesen Index, um das Energiesystem zu erstellen
my_energysystem = solph.EnergySystem(timeindex=my_index, infer_last_interval=True)

# Buses definieren und hinzufügen
bel_ac = solph.buses.Bus(label='electricity_ac')
bel_dc = solph.buses.Bus(label='electricity_dc')
bhydr_30 = solph.buses.Bus(label="h2_30bar")
bhydr_700 = solph.buses.Bus(label="h2_700bar")

my_energysystem.add(bel_ac, bel_dc, bhydr_700, bhydr_30)


# Using an AC-DC bus with efficiency 1:1 allows me to check whether my "efficiency" in the energy for the compressor is
# correctly used
my_energysystem.add(create_simple_inverter(input_bus=bel_ac, output_bus=bel_dc, efficiency=1.0, label='1to1'))


# Verdichter
# Hier kann man den Throughput testen, indem man für nominal_power_in_kg_per_h einmal 1.48 und einmal 1.52 einträgt,
# da bei 50 kW Leistung (CSV File) 1.5 kg/h benötigt werden (50 kW / 33.33 kWh/kg = 1.5 kg/h)
# -> das eine (1.48) sollte infeasible sein und das andere (1.52) problemlos durchlaufen

# JETZT NEU: statt compression_energy_to_hhv=0.13 nutz ich den absoluten wert in kW: 0.13*39.4 = 5.122 kWh
my_energysystem.add(create_compressor_a(input_bus_h2=bhydr_30, output_bus_h2=bhydr_700,
                                        electrical_bus=bel_dc,
                                        compression_energy_kwh_per_kg=5.122,
                                        nominal_power_in_kg_per_h=1.51,
                                        label='compressor'))

### 1:1 Converter Test ###
bhydr_700_1_1 = solph.Bus(label='h2_700bar_1_1')
my_energysystem.add(bhydr_700_1_1)
my_energysystem.add(solph.components.Converter(
        label="H2_350_from_compressor_to_350",
        inputs={bhydr_700: solph.Flow()},
        outputs={bhydr_700_1_1: solph.Flow()}))

#######################

datapath = os.path.join(os.path.dirname(__file__), "..", "MA_Fallbeispiele", "daten")
file_path = os.path.join(datapath, "einfacher_verbraucher_50_impuls.csv")


fcev_normalized_ts = import_and_normalize_one_day_time_series_csv(csv_path=file_path,
                                                                  base_sim_interval_in_min=freq_in_min)

my_energysystem.add(solph.components.Sink(label='Demand_FCEV',
                             inputs={bhydr_700: solph.flows.Flow(
                                 fix=fcev_normalized_ts,
                                 nominal_value=1)}))

# EXZESS WÄRME
#my_energysystem.add(solph.components.Sink(label="excess_bth", inputs={bth: solph.Flow()}))

DUMMY_PRICE_PER_KWH = 0.3  # EUR/kWh

# Energy Source / grid; hier als DC, nur für testing
s_electric_grid_buy = solph.components.Source(
    label="s_el_grid_buy",
    outputs={
        bel_ac: solph.Flow(
            variable_costs=[DUMMY_PRICE_PER_KWH] * ((
                                                                24 * 60) // freq_in_min + 1))})  # create_const_time_series(DUMMY_PRICE_PER_KWH, freq_in_min))})#ts_marktpreis_euro_per_mwh)})  # EUR/kWh

# analog fuer den H2
H2_PRICE = 9.50  # EUR/kg. Erstmal nur grob den Tankpreis aus 2020 https://www.dihk.de/resource/blob/24872/fd2c89df9484cf912199041a9587a3d6/energie-dihk-faktenpapier-wasserstoff-data.pdf Seite 10
H2_PRICE_PER_EQUIV_kWh = H2_PRICE / convert_kg_H2_to_kWh(
    1)  # kWh pro kg H2 (etwa 33.3) -> H2_PRICE per kg durch das teilen -> EUR / kWh
s_h2_grid_buy = solph.components.Source(
        label="s_h2_grid",
        outputs={
            bhydr_30: solph.Flow(
                variable_costs=[H2_PRICE_PER_EQUIV_kWh]*((24*60)//freq_in_min + 1))})#create_const_time_series(H2_PRICE_PER_EQUIV_kWh, freq_in_min))})  # EUR/kWh

my_energysystem.add(s_h2_grid_buy, s_electric_grid_buy)

# Energysystem plotten
gr = ESGraphRenderer(energy_system=my_energysystem, filepath="../energy_system_test_VERDICHTER", img_format="pdf")
gr.view()

# initialise operational model (create problem)
om = solph.Model(my_energysystem)

# set tee to True to get solver output
om.solve(solver='cbc', solve_kwargs={'tee': True})

# get results
# my_energysystem.results = processing.results(om)
my_energysystem.results["main"] = solph.processing.results(om)
my_energysystem.results["meta"] = solph.processing.meta_results(om)
# my_energysystem.dump('my_path', 'my_dump.oemof')

## begin plot examplez nach https://github.com/oemof/oemof-examples/blob/master/oemof_examples/oemof.solph/v0.4.x/basic_example/basic_example.py
# define an alias for shorter calls below (optional)
results = my_energysystem.results["main"]

ac_bus = solph.views.node(results, "electricity_ac")
dc_bus = solph.views.node(results, "electricity_dc")
h2_bus_30 = solph.views.node(results, "h2_30bar")
h2_bus_700 = solph.views.node(results, "h2_700bar")
h2_bus_700 = solph.views.node(results, "h2_700bar_1_1")

plot_data(dc_bus, h2_bus_30, h2_bus_700, legend_names=["electricity_dc", "h2_30bar", "h2_700bar"])
plot_data(dc_bus, h2_bus_30, h2_bus_700, legend_names=["electricity_dc", "h2_30bar", "h2_700bar_1_1"])
plot_data(ac_bus, dc_bus, h2_bus_700, legend_names=["electricity_dc", "electricity_ac", "h2_700bar"])

print("DONE")

