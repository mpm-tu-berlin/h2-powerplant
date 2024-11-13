# Experiment 3A - Spotmarktpreis: Mittelwert und Varianz erhöhen
# Netzentgelte WERDEN berechnet. Alles wie im Base Case.


import copy
import json
import os.path
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

import MA_Fallbeispiele.commonFunctions as h2ppcf
from h2pp.optimizer import prep_sim_config_dict, eval_scenario

####################################################################################################################

datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

ergebnis_path = os.path.join(os.path.dirname(__file__), "..", "plot_results_for_ma")


####################################################################################################################



datapath_common_data = os.path.join(os.path.dirname(__file__), "..", "Common_Data")
file_path_base_spotprice = os.path.join(datapath_common_data, 'Spotmarktpreis DEU 2023-09 bis 2024-08.csv')

# Create a new directory (actually a directory in the same folder as the script..)
# if not already exists
output_dir = os.path.join(os.path.dirname(__file__), 'temp_folder_output_power_prices_altered_000')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Create scenarios with increased mean and variance
# in cent

m_inc = [0, 3, 6, 10, 15]
v_inc = [0, 30, 50, 100]

for mean_increase in m_inc:
    for variance_increase in v_inc: # prozentual, 30 = Varianz Streckung mit Wert 1.3
        output_file = os.path.join(output_dir, f'Var_Prices_M{mean_increase}_V{variance_increase}.csv')
        h2ppcf.increase_mean_and_variance_in_netztransparenz_power_price_file(strompreis_file_path=file_path_base_spotprice,
                                                                              streckungsfaktor= 1+(variance_increase/100),
                                                                              mean_steigerung=mean_increase,
                                                                              output_file=output_file)


with open(file_path) as user_file:
    parsed_json = json.load(user_file)


# Disable Netzentgelte und Abzüge
# parsed_json['nur_beschaffungskosten'] = True
# parsed_json['abzugbetrag_strom_in_ct'] = 0.183

scenario_base = copy.deepcopy(parsed_json)

# Bessere Wirkungsgrade und mehr Kapazität für FC + EL, höherer Tank
# Brennstoffzelle: 30% th. lassen; aber elektr. hoch auf 60%:
# (für SOFC realistisch siehe https://gas.info/fileadmin/Public/PDF-Download/Brennstoffzelle-Waermeerzeugung.pdf)
scenario_bessere_wirkungsgrade = copy.deepcopy(parsed_json)
scenario_bessere_wirkungsgrade['fuelcell']['efficiency_electric'] = 0.6
# Elektrolyseur so 85% annehmen (für SOE durchaus realistisch)
scenario_bessere_wirkungsgrade['electrolyzer']['efficiency'] = 0.85

scenario_bessere_eta_plus_hoeher_dimensioniert_ev = copy.deepcopy(parsed_json)
scenario_bessere_eta_plus_hoeher_dimensioniert_ev['fuelcell']['fixed_p'] = 200
scenario_bessere_eta_plus_hoeher_dimensioniert_ev['electrolyzer']['fixed_p'] = 500
scenario_bessere_eta_plus_hoeher_dimensioniert_ev['tank']['fixed_capacity'] = 1000
h2ppcf.config_dict_ev_change(scenario_bessere_eta_plus_hoeher_dimensioniert_ev, False)

scenarios = [scenario_base, scenario_bessere_wirkungsgrade, scenario_bessere_eta_plus_hoeher_dimensioniert_ev]
scenario_names = ['Base', 'Bessere Wirkungsgrade', 'Eta höher + höhere Dimensionierung + EV statt FCEV']

for scen, mode in [(scenario_bessere_eta_plus_hoeher_dimensioniert_ev, "normal"),
                   (scenario_bessere_wirkungsgrade, "normal"),
                   (scenario_base, "normal"),
                   (scenario_base, "battery_ref")]:
    scenario_name = scenario_names[scenarios.index(scen)]
    for mode in ("normal", "battery_ref"):
        all_graphs = []
        for mean_increase in m_inc:
            copied_json = copy.deepcopy(scen)  # Copy the dictionary to avoid changing the original
            path_values = [f"../04_Sensitivitaetsanalysen/temp_folder_output_power_prices_altered_000/Var_Prices_M{mean_increase}_V{variance_increase}.csv"
                           for variance_increase in v_inc]

            # Gruppiert nach Mean Increase = Die Scenarios,
            # müssen wir die Variance erhöhen.
            # Ist der Filename, also eig überall es durch pro

            tcos = h2ppcf.calc_tco_sensitivity(copied_json, datapath, path_values, ['strompreis_csv'], optimizer_mode=mode)
            list_of_tco_npvs = [tco.npv_total for tco in
                                tcos]
            all_graphs.append(list_of_tco_npvs)



        # Now plot in matplotlib the x_values against the list_of_tco_npvs
        # Plotting
        plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
        for i, list_of_tco_npvs in enumerate(all_graphs):
            z_value = m_inc[i]
            plt.plot(v_inc, list_of_tco_npvs, label=f'Mean Increase = {z_value}')

        # Adding labels and title
        plt.xlabel('Variance Increase in Percent')  # Customize your x-axis label
        plt.ylabel('NPV in EUR')  # Customize your y-axis label
        plt.legend()
        plt.title(f'Modifikation von Mean und Varianz des Strompreises: \n {mode}; {scenario_names[n]}')  # Customize your plot title

        # Optionally add grid
        plt.grid(True)

        # Display the plot
        plt.savefig(os.path.join(ergebnis_path, "Exp_4E_Sensitivity_Strompreise.pdf"))
        plt.show()
