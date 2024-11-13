import os

import pandas as pd
import oemof.solph as solph

from h2pp.oemof_visio_energy_system_graph import ESGraphRenderer


import matplotlib.pyplot as plt

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
#bel_ac = solph.buses.Bus(label='electricity_ac')
bel_dc = solph.buses.Bus(label='electricity_dc')
bth = solph.buses.Bus(label="thermal")
bhydr_700 = solph.buses.Bus(label="h2_700bar")

my_energysystem.add(bel_dc, bhydr_700, bth)


# Brennstoffzelle
# Kraft-Wärme-Kopplung / BHKW: CHP (Combined Heat and Power)
# Hierfür benutze ich erstmal Werte aus https://www.energy.gov/eere/amo/articles/fuel-cells-doe-chp-technology-fact-sheet-series-fact-sheet-2016, einfach System 1 erstmal
eta_fc_el = 0.425
eta_fc_th = 0.327
leistung_brennstoffzelle = 76.5  # kW
my_energysystem.add(create_fuel_cell_chp(input_bus_h2=bhydr_700,
                                         output_bus_el=bel_dc,
                                         output_bus_th=bth,
                                         electrical_efficiency=eta_fc_el,
                                         thermal_efficiency=eta_fc_th,
                                         nominal_power_el=leistung_brennstoffzelle))


datapath = os.path.join(os.path.dirname(__file__), "..", "MA_Fallbeispiele", "daten")
file_path = os.path.join(datapath, "einfacher_verbraucher_50_impuls.csv")

ev_normalized_ts = import_and_normalize_one_day_time_series_csv(csv_path=file_path,
                                                                base_sim_interval_in_min=freq_in_min)

my_energysystem.add(solph.components.Sink(label='Demand_EV',
                             inputs={bel_dc: solph.flows.Flow(
                                 fix=ev_normalized_ts,
                                 nominal_value=1)}))


# EXZESS WÄRME
my_energysystem.add(solph.components.Sink(label="excess_bth", inputs={bth: solph.Flow()}))
# my_energysystem.add(solph.components.Sink(label="excess_h2", inputs={bhydr_700: solph.Flow()}))
#my_energysystem.add(solph.components.Sink(label="excess_bel", inputs={bel_dc: solph.Flow()}))

DUMMY_PRICE_PER_KWH = 0.3  # EUR/kWh

# Energy Source / grid; hier als DC, nur für testing
# s_electric_grid_buy = solph.components.Source(
#     label="s_el_grid_buy",
#     outputs={
#         bel_dc: solph.Flow(
#             variable_costs=[DUMMY_PRICE_PER_KWH] * ((
#                                                                 24 * 60) // freq_in_min + 1))})  # create_const_time_series(DUMMY_PRICE_PER_KWH, freq_in_min))})#ts_marktpreis_euro_per_mwh)})  # EUR/kWh

# analog fuer den H2
H2_PRICE = 9.50  # EUR/kg. Erstmal nur grob den Tankpreis aus 2020 https://www.dihk.de/resource/blob/24872/fd2c89df9484cf912199041a9587a3d6/energie-dihk-faktenpapier-wasserstoff-data.pdf Seite 10
H2_PRICE_PER_EQUIV_kWh = H2_PRICE / convert_kg_H2_to_kWh(
    1)  # kWh pro kg H2 (etwa 33.3) -> H2_PRICE per kg durch das teilen -> EUR / kWh
s_h2_grid_buy = solph.components.Source(
        label="s_h2_grid",
        outputs={
            bhydr_700: solph.Flow(
                variable_costs=[H2_PRICE_PER_EQUIV_kWh]*((24*60)//freq_in_min + 1))})#create_const_time_series(H2_PRICE_PER_EQUIV_kWh, freq_in_min))})  # EUR/kWh

my_energysystem.add(s_h2_grid_buy)

# Energysystem plotten
gr = ESGraphRenderer(energy_system=my_energysystem, filepath="../energy_system_test_BZ", img_format="pdf")
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

electricity_bus = solph.views.node(results, "electricity_dc")
thermal_bus = solph.views.node(results, "thermal")
h2_bus = solph.views.node(results, "h2_700bar")

plot_data(electricity_bus, thermal_bus, h2_bus, legend_names=["electricity_dc", "thermal", "h2_700bar"])

print("DONE")

