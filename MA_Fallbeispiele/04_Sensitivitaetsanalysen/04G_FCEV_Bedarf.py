import copy
import json
import os.path
import numpy as np

from MA_Fallbeispiele import commonFunctions as h2ppcf

####################################################################################################################

datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

ergebnis_path = os.path.join(os.path.dirname(__file__), "..", "plot_results_for_ma")

exp_name = "Exp_04G_DG"

####################################################################################################################


datapath_common_data = os.path.join(os.path.dirname(__file__), "..", "Common_Data")
file_path_base_spotprice = os.path.join(datapath_common_data, 'Spotmarktpreis DEU 2023-09 bis 2024-08.csv')

# Create scenarios with increased mean and variance
# in cent

dateien = ["fcev_dummy_time_series_only_weekdays.csv",
           "fcev_equiv_dummy_ts_halber_bedarf_only_weekdays.csv",
            "fcev_equiv_dummy_ts_drittel_bedarf_only_weekdays.csv",
            "fcev_equiv_dummy_ts_sechstel_bedarf_only_weekdays.csv"]

scen_names = ["Normaler Bedarf",
              "Halber Bedarf",
              "Drittel des Bedarfs",
              "Sechstel des Bedarfs"]

with open(file_path) as user_file:
    parsed_json = json.load(user_file)


scenarios = []

for dateiname in dateien:
    scen = copy.deepcopy(parsed_json)
    path_value = f"../Common_Data/bev_fcev_without_weekends/{dateiname}"
    for consumer in scen['consumers']:
        if consumer['name'] == 'timeseries_fcev':
            consumer['parameters']['file_path'] = path_value
    scenarios.append(scen)


#scenario_ohne_ne = copy.deepcopy(parsed_json)
#scenario_ohne_ne['nur_beschaffungskosten'] = True

#scenarios = [scenario_base, scenario_ohne_ne]
#scenario_names = ['Normal', 'Ohne Netzentgelte usw.']


h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=scenarios, original_folder_path=datapath,
                                          scenario_labels=scen_names,
                                     x_values=np.linspace(0, 600, 11),
                                     key_path_x=['electrolyzer', 'fixed_p'],
                                     plot_title=f'TCO bei verschiedenen FCEV Bedarfen und Elektrolyseurleistungen',
                                     plot_x_label=r'$p_{ES} in kW$',
                                      exp_name=exp_name,
                                      file_name_prefix="Variation_FCEV_Bedarf_mit_Entgelten")

# Netzentgelte deaktivieren bei allen
for scenario in scenarios:
    scenario['nur_beschaffungskosten'] = True

h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=scenarios, original_folder_path=datapath,
                                          scenario_labels=scen_names,
                                          x_values=np.append([0, 25, 37.5, 50, 62.5, 75, 100, 125], np.linspace(150,500,8)),
                                          key_path_x=['electrolyzer', 'fixed_p'],
                                          plot_title=f'TCO bei verschiedenen FCEV Bedarfen und Elektrolyseurleistungen \n ohne Netzentgelte',
                                          plot_x_label=r'$p_{ES} in kW$',
                                          exp_name=exp_name,
                                          file_name_prefix="Variation_FCEV_Bedarf_ohne_Entgelte")
