import copy
import json

import numpy as np
from matplotlib import pyplot as plt

from h2pp import optimizer, tco
from h2pp.optimizer import optimize_h2pp
from h2pp.simulation import run_simulation
import MA_Fallbeispiele.commonFunctions as h2ppcf
import os

# Base JSON:
the_json_filename = "generated_ts_config_euref_dus.json"
# generated_ts_config_euref_dus.json # input_dus.json

exp_name = "Exp_04X"

ergebnis_path = os.path.join(os.path.dirname(__file__), "..", "plot_results_for_ma")

# Create folder Exp_04X if not existing in ergebnis_path
exp_folder = os.path.join(ergebnis_path, exp_name)
if not os.path.exists(exp_folder):
    os.makedirs(exp_folder)



import os
# Basic Simulation
# Achtung, geänderte Annahmen, siehe MA.. Vor allem jetzt auch am WE keine Fahrzeugbetankungen mehr..
datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, the_json_filename)


with open(file_path) as user_file:
    parsed_json = json.load(user_file)

parsed_json['nur_beschaffungskosten'] = True

aufschlaege = [0, 8] + list(range(9, 26)) # Beschleunigung der Simulation weil die ersten paar cents eh zu 0 evaluieren (Vorwissen)
print(aufschlaege)
h2_kosten_ges = []

for aufschlag_ct in aufschlaege:
    copied_json = copy.deepcopy(parsed_json)  # Copy the dictionary to avoid changing the original
    copied_json['aufschlag_strom_manuell_ct'] = aufschlag_ct

    output_file_path = os.path.join(file_path, "..", "__tempA_sensitivity_analysis.json")
    rp = os.path.realpath(output_file_path)
    print(copied_json)
    with open(rp, "w") as user_file:  # may NOT exist or will be overwritten
        json.dump(copied_json, user_file, indent=4)

    tco, _ = optimize_h2pp(rp, mode="normal")
    anteil_h2_buy = tco.sum_cash_flows_npv["OPEX"]["H2_Buy"]
    h2_kosten_ges.append(anteil_h2_buy / 1e6)  # in Mio €

plt.plot(aufschlaege, h2_kosten_ges)
plt.xlabel("Aufschlag Strompreis in ct/kWh")
plt.ylabel("Gesamtkosten für H2 in Mio €")
#plt.title("H2 Kosten in Abhängigkeit des Strompreisaufschlags")


h2ppcf.create_export_folder(exp_name)
plt.savefig(os.path.join(exp_folder, "result.pdf"))
plt.show()



####

# h2ppcf.fuenffach_analyse(datapath, file_path, exp_name, ev_usage_on_weekends=False)

###
