import copy
import json
import os
import numpy as np

from h2pp.optimizer import prep_sim_config_dict, eval_scenario
import MA_Fallbeispiele.commonFunctions as h2ppcf

# =======================================================================================================================

datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

# =======================================================================================================================

alle_ergebnisse = {}

with open(file_path) as user_file:
    parsed_json = json.load(user_file)

exp_name = "Exp_04H"

parsed_json_keine_st_ne = copy.deepcopy(parsed_json)
parsed_json_keine_st_ne["nur_beschaffungskosten"] = True

parsed_json_10ct_aufschlag = copy.deepcopy(parsed_json)
parsed_json_10ct_aufschlag["nur_beschaffungskosten"] = True
parsed_json_10ct_aufschlag['aufschlag_strom_manuell_ct'] = 10

the_scenarios = [parsed_json, parsed_json_keine_st_ne, parsed_json_10ct_aufschlag]
scenario_names = ['Basisszenario', 'Ohne_Netzentgelte_usw', 'Manuell_10ct_Aufschlag']

####################################################################################################################


# Elektrolyseur Wirkungsgrade
for i, scenario in enumerate(the_scenarios):
    # Für JEDES der drei Szenarien machen wir Unterszenarien für variable FC-Wirkungsgrade (el. UND th.)
    # danach dann nochmal für den Fall "ohne FCEV Flotte"

    subscenarios = []
    subscenario_names = []
    for eta_el, eta_th in [(0.5, 0.3), (0.7, 0.3), (0.8, 0.2), (1.0, 0.0)]:
        subscen = copy.deepcopy(scenario)
        subscen['fuelcell']['efficiency_electric'] = eta_el
        subscen['fuelcell']['efficiency_thermal'] = eta_th
        descr_string = r"$\eta_{FC,el}$: " + str(eta_el) + r", $\eta_{FC,th}$: " + str(eta_th)
        subscenario_names.append(descr_string)
        subscenarios.append(subscen)


    for j in [0,1]:

        if j == 1:
            # FCEV Flotte entfernen bei allen Wirkungsgradszenarien und erneut berechnen
            for subscen in subscenarios:
                subscen['consumers'] = [consumer for consumer in subscen['consumers'] if
                                        consumer['name'] != 'timeseries_fcev']

        appendix = "mit_FCEV" if j == 0 else "ohne_FCEV"

        h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=subscenarios, scenario_labels=subscenario_names,
                                                  original_folder_path=datapath,
                                                  x_values=np.linspace(0.55, 1.0, 10),
                                                  key_path_x=['electrolyzer', 'efficiency'],
                                                  plot_title=f'Kosten bei variablen Wirkungsgraden - {scenario_names[i]}',
                                                  plot_x_label="$\eta_{ES}$",
                                                  hide_grid=False,
                                                  exp_name=exp_name,
                                                  file_name_prefix=f"Wirkungsgrade_ES_FC_{scenario_names[i]}_{appendix}")


