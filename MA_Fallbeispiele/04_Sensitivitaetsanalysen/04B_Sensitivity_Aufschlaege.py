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

parsed_json["nur_beschaffungskosten"] = True
exp_name = "Exp_04B"
#parsed_json_10ct_aufschlag['aufschlag_strom_manuell_ct'] = 10


#the_scenarios = [parsed_json, parsed_json_keine_st_ne, parsed_json_10ct_aufschlag]
#scenario_names = ['Basisszenario', 'Ohne Steuern, Abgaben, Entgelte', 'Manuell 10ct/kWh Aufschlag']

####################################################################################################################

# TODO hier könnte auch eine Gegenüberstellung mit dem Szenario ohne H2PP erfolgen, um zu sehen ab welcher Abgabenlast es sich nicht mehr lohnt.
h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                                     x_values=np.linspace(0, 25, 10), # todo evtl. nur bis 20 ct/kWh sähe besser aus?
                                     z_values=[100, 500], #[100, 228, 335],
                                     key_path_x=['aufschlag_strom_manuell_ct'],
                                     key_path_z=['electrolyzer', 'fixed_p'],
                                     plot_title=f'TCO nach Strom-Aufschlägen/Entgelten',
                                     plot_x_label=r'$ct/kWh$',
                                     plot_z_label=r'$p_{ES}$',
                                      exp_name=exp_name,
                                      file_name_prefix="TCO_nach_Aufschlaegen")


#for i, scenario in enumerate(the_scenarios):
#    h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=scenario, original_folder_path=datapath,
#                        config_file_full_path=datapath, optimizer_mode="normal",
#                          x_values=np.linspace(150, 2000, 3),
#                          key_path=['electrolyzer', 'fixed_p'],
 #                         plot_title=f'Variation Elektrolyseurleistung - {scenario_names[i]}',
 #                         plot_x_label=r'$p_{EL} in kW')
