# Erstmal testen wie viel Leistung die Komponenten maximal beanspruchen, wenn wir SEHR hoch dimensionieren::
import copy
import json
import os

import numpy as np
from matplotlib import pyplot as plt

from MA_Fallbeispiele.commonFunctions import calc_tco_sensitivity
from h2pp.optimizer import optimize_h2pp

datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

exp_name = "Exp_04F"

ergebnis_path = os.path.join(os.path.dirname(__file__), "..", "plot_results_for_ma", exp_name)

# Create folder if not existing in ergebnis_path
exp_folder = os.path.join(ergebnis_path, exp_name)
if not os.path.exists(exp_folder):
    os.makedirs(exp_folder)


# alter our dict!
with open(file_path) as user_file:
    parsed_json = json.load(user_file)

# Anpassungen
parsed_json["electrolyzer"]["fixed_p"] = 2000
parsed_json["fuelcell"]["fixed_p"] = 1000
parsed_json["tank"]["fixed_capacity"] = 2000

# Zurück schrei
file_path_out = os.path.join(datapath, '__temp_file_cost_capex_analysi.json')  # may NOT exist or will be overwritten
with open(file_path_out, "w") as user_file:
    json.dump(parsed_json, user_file, indent=4)


tco_normal, figs = optimize_h2pp(file_path_out, mode="normal")
tco_normal.plot_stacked_bar_over_period().show()
figs["SOMMER"].show()
figs["UEBERGANG"].show()
figs["WINTER"].show()

# delete the file
os.remove(file_path_out)

####################################################################################################################

with open(file_path) as user_file:
    parsed_json = json.load(user_file)

# Anpassungen

for nur_beschaffungskosten_bool in [False, True]:
    for electrolyzer_p in [200, 700]:
        # 560 kg should be sufficient..:
        # 5*20*5.6 kg (5 days, 20 cars each day, 5.6 kg per car for full tank)

        parsed_json["nur_beschaffungskosten"] = nur_beschaffungskosten_bool
        parsed_json["fuelcell"]["fixed_p"] = 0 # assume it is not used.
        parsed_json["electrolyzer"]["fixed_p"] = electrolyzer_p

        x_values = np.append(np.linspace(0,700,8), np.linspace(800,2000,7))
        list_of_tcos = calc_tco_sensitivity(parsed_json, datapath, x_values, ["tank", "fixed_capacity"], "normal")

        all_graphs = []
        z_values = [200, 634, 1000] # Values for CAPEX Base Price
        for z_value in z_values:
            new_tco_npvs = []
            for tco_alt in list_of_tcos:
                # TCO change will only alter the total cost but NOT the control strategy.
                # Therefore we only must run the optimizer once for each power value of electrolyzer / capacity of tank and can then change the cost data
                new_tco = copy.deepcopy(tco_alt)
                new_cost_data = new_tco.cost_data  # get old cost data

                # modify prices for electrolyzer
                new_cost_el = z_value
                new_cost_data["CAPEX"]["Tank_LP"]["unit_cost"] = new_cost_el
                new_cost_data["OPEX"]["OMC_Tank_LP"]["unit_cost"] = new_cost_el * 0.01
                new_tco.cost_data = new_cost_data # will directly force NPV recalculation (see setter function for cost_data in tco.py)
                new_tco_npvs.append(new_tco.npv_total / 1e6)

            all_graphs.append(new_tco_npvs)


        # Now plot in matplotlib the x_values against the list_of_tco_npvs
        # Plotting
        plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
        for i, list_of_tco_npvs in enumerate(all_graphs):
            z_value = z_values[i]
            plt.plot(x_values, list_of_tco_npvs, label =f'Kosten Niederdruckspeicher in EUR/kg = {z_value}')

        # Adding labels and title
        plt.xlabel("Tankkapazität in kg")
        plt.ylabel('NPV in Mio. EUR')
        plt.legend()

        # Optionally add grid
        plt.grid(True)

        plt.savefig(os.path.join(ergebnis_path, f"Varying_Tank_Costs_Netzentgelte_ignorieren_{nur_beschaffungskosten_bool}_EL{electrolyzer_p}kW.pdf"))

        # Title only in the displayed plot, not the exported one
        plt.title(
            f"Variation Kosten Tank - Steuern/Netzentgelte/etc ignorieren: {nur_beschaffungskosten_bool}, p_ES: {electrolyzer_p} kW")

        # Display the plot
        plt.show()




for nur_beschaffungskosten_bool in [False, True]:
    for tank_capacity in [200, 560, 1000]:
        # 560 kg should be sufficient..:
        # 5*20*5.6 kg (5 days, 20 cars each day, 5.6 kg per car for full tank)

        parsed_json["nur_beschaffungskosten"] = nur_beschaffungskosten_bool
        parsed_json["fuelcell"]["fixed_p"] = 0 # assume it is not used.
        parsed_json["tank"]["fixed_capacity"] = tank_capacity # 5*20*5.6 kg (5 days, 20 cars each day, 5.6 kg per car for full tank)

        x_values = np.linspace(0, 2000, 10)
        list_of_tcos = calc_tco_sensitivity(parsed_json, datapath, x_values, ["electrolyzer", "fixed_p"], "normal")

        all_graphs = []
        z_values = [500, 1200, 2000, 3000] # Values for CAPEX Base Price
        for z_value in z_values:
            new_tco_npvs = []
            for tco_alt in list_of_tcos:
                # TCO change will only alter the total cost but NOT the control strategy.
                # Therefore we only must run the optimizer once for each power value of electrolyzer / capacity of tank and can then change the cost data
                new_tco = copy.deepcopy(tco_alt)
                new_cost_data = new_tco.cost_data  # get old cost data

                # modify prices for electrolyzer
                new_cost_el = z_value
                new_cost_data["CAPEX"]["Elektrolyseur"]["unit_cost"] = new_cost_el
                new_cost_data["OPEX"]["OMC_Elektrolyseur"]["unit_cost"] = new_cost_el * 0.02
                new_tco.cost_data = new_cost_data # will directly force NPV recalculation (see setter function for cost_data in tco.py)
                new_tco_npvs.append(new_tco.npv_total / 1e6)

            all_graphs.append(new_tco_npvs)


        # Now plot in matplotlib the x_values against the list_of_tco_npvs
        # Plotting
        plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
        for i, list_of_tco_npvs in enumerate(all_graphs):
            z_value = z_values[i]
            plt.plot(x_values, list_of_tco_npvs, label =f'Elektrolyseurkosten in EUR/kW = {z_value}')

        # Adding labels and title
        plt.xlabel("Elektrolyseurleistung in kW")
        plt.ylabel('NPV in Mio. EUR')
        plt.legend()

        # Optionally add grid
        plt.grid(True)

        # Export the plot
        plt.savefig(os.path.join(ergebnis_path, f"Varying_EL_Costs_Netzentgelte_ignorieren_{nur_beschaffungskosten_bool}_Tank{tank_capacity}kg.pdf"))

        # Title only in the displayed plot, not the exported one
        plt.title(
            f"Variation Elektrolyseurkosten - Steuern/Netzentgelte/etc ignorieren: {nur_beschaffungskosten_bool}, Tankkapazität: {tank_capacity} kg")

        plt.show()



