# Prepare EV json
import copy
import json
import os
import shutil
import tempfile

import numpy as np
from matplotlib import pyplot as plt

from MA_Fallbeispiele.commonFunctions import calc_tco_sensitivity, config_dict_ev_change

# =======================================================================================================================

datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

ergebnis_path = os.path.join(os.path.dirname(__file__), "..", "plot_results_for_ma")

# Create folder Exp_04A if not existing in ergebnis_path
exp_folder = os.path.join(ergebnis_path, "Exp_04A")
if not os.path.exists(exp_folder):
    os.makedirs(exp_folder)


# Modify the config file
with open(file_path) as user_file:
    parsed_json = json.load(user_file)

# Netzentgelte deaktiviert
parsed_json['nur_beschaffungskosten'] = True


c_dict_fcev = copy.deepcopy(parsed_json)

# also prepare EV dict
c_dict_ev = copy.deepcopy(parsed_json)
config_dict_ev_change(c_dict_ev, usage_on_weekends=False)


x_values = np.linspace(0, 26, 14)
key_path_x = ['aufschlag_strom_manuell_ct']
# todo rausziehen der calc_tco_sensitivity
list_of_grid_fcev_tcos = [tco.npv_total / 1e6 for tco in calc_tco_sensitivity(c_dict_fcev, datapath, x_values, key_path_x, optimizer_mode="power_grid_only_ref")]
list_of_grid_bev_tcos = [tco.npv_total / 1e6 for tco in calc_tco_sensitivity(c_dict_ev, datapath, x_values, key_path_x, optimizer_mode="power_grid_only_ref")]
list_of_h2pp_tcos = [tco.npv_total / 1e6 for tco in calc_tco_sensitivity(c_dict_fcev, datapath, x_values, key_path_x, optimizer_mode="normal")]
list_of_battery_fcev_tcos = [tco.npv_total / 1e6 for tco in calc_tco_sensitivity(c_dict_fcev, datapath, x_values, key_path_x, optimizer_mode="battery_ref")]
list_of_battery_bev_tcos = [tco.npv_total / 1e6 for tco in calc_tco_sensitivity(c_dict_ev, datapath, x_values, key_path_x, optimizer_mode="battery_ref")]

all_graphs = [list_of_h2pp_tcos, list_of_battery_fcev_tcos, list_of_battery_bev_tcos, list_of_grid_fcev_tcos, list_of_grid_bev_tcos]
all_names = ["H2PP", "Battery + FCEV", "Battery + BEV", "Only Grid + FCEV", "Only Grid + BEV"]
# Now plot in matplotlib the x_values against the list_of_tco_npvs
# Plotting
plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
for i, list_of_tco_npvs in enumerate(all_graphs):
    z_value = all_names[i]

    plt.plot(x_values, list_of_tco_npvs, label=z_value)

# Adding labels and title
plt.xlabel("Aufschlag Strompreis in ct/kWh")  # Customize your x-axis label
plt.ylabel('NPV in Mio. EUR')  # Customize your y-axis label
plt.legend()
#plt.title("Sensitivität der Steuer-/Abgabelast der einzelnen Szenarien")  # Customize your plot title

# Optionally add grid
plt.grid(True)

# Display the plot
plt.savefig(os.path.join(exp_folder, "Sensitivity_Netzentgelte_vs_Referenzfaelle.pdf"))
plt.show()
