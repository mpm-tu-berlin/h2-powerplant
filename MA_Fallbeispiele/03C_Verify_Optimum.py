"""
Validierung der Ergebnisse aus der Optimierung in 03_B durch Sensitivitätsanalysen um die gefundenen Optima herum.
Die gefundenen Optimalwerte werden unten eingetragen
"""

import json
import os
import warnings

import numpy as np

from h2pp.optimizer import prep_sim_config_dict, eval_scenario
import MA_Fallbeispiele.commonFunctions as h2ppcf

# =======================================================================================================================

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

# =======================================================================================================================

# Parameter des "Optimums"
fixed_p_el = 228
fixed_p_fc = 0
fixed_capacity_tank = 164
compress_before_storing = True
nur_beschaffungskosten = True

####################################################################################################################

warnings.warn("Before continuing, make sure you have altered the values in the script to the current found optimum")
input("Press ENTER to continue..")

with open(file_path) as user_file:
    parsed_json = json.load(user_file)

exp_name = "Exp_03C"


# Propagate optima values
parsed_json["electrolyzer"]["fixed_p"] = fixed_p_el
parsed_json["fuelcell"]["fixed_p"] = fixed_p_fc
parsed_json["tank"]["fixed_capacity"] = fixed_capacity_tank
parsed_json["tank"]["compress_before_storing"] = compress_before_storing

parsed_json["tank"]["hp_tank_capacity_kg"] = 56
parsed_json["tank"]["throughput_50bar_compressor_kg_per_hour"] = 56

parsed_json["nur_beschaffungskosten"] = nur_beschaffungskosten


####################################################################################################################

h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                          x_values=np.linspace(170, 280, 12),
                          key_path=['electrolyzer', 'fixed_p'],
                          plot_title=f'Variation Elektrolyseur bei m_Tank = {fixed_capacity_tank} kg',
                          plot_x_label=r'$p_{ES}$ in kW',
                                 exp_name=exp_name,
                                 file_name_prefix="EL_solo_A")

h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                          x_values=np.linspace(100, 200, 11),
                          key_path=['tank', 'fixed_capacity'],
                          plot_title=f'Variation Tank bei p_ES = {fixed_p_el} kW',
                          plot_x_label=r'$m_{Tank}$ in kg',
                                 exp_name=exp_name,
                                 file_name_prefix="Tank_solo_A")

# FC konstant, Elektrolyseur und Tank variabel, mit Elektrolyseur gruppiert und Tank kontinuierlich
h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                        x_values=np.linspace(0, 500, 11), # Tank
                        z_values=[100, 200, 400, 600], # Elektrolyseur
                        key_path_x=['tank', 'fixed_capacity'],
                        key_path_z=['electrolyzer', 'fixed_p'],
                        plot_x_label=r'$m_{Tank}$ in kg',
                        plot_z_label=r'$p_{ES}$ in kW ',
                        plot_title=f'Variation Tankkapazität bei verschiedenen Elektrolyseurleistungen \n und p_FC = {fixed_p_fc} kW',
                                      exp_name=exp_name,
                                      file_name_prefix="Tank_vs_EL_Groupby_EL_A")

# FC konstant, Elektrolyseur und Tank variabel

h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                        x_values=np.linspace(0, 400, 9), # Elektrolyseur
                        z_values=[100, 200, 500, 1000], # Tank
                        key_path_x=['electrolyzer', 'fixed_p'],
                        key_path_z=['tank', 'fixed_capacity'],
                        plot_x_label=r'$p_{ES}$ in kW',
                        plot_z_label=r'$m_{Tank}$ in kg ',
                        plot_title=f'Variation Elektrolyseurleistung und Tank bei p_FC = {fixed_p_fc} kW',
                        exp_name=exp_name,
                        file_name_prefix="EL_vs_Tank_Groupby_Tank_A")


h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                        x_values=np.linspace(0, 2000, 11), # Elektrolyseur
                        z_values=[0, 100, 200, 500], # Tank
                        key_path_x=['electrolyzer', 'fixed_p'],
                        key_path_z=['tank', 'fixed_capacity'],
                        plot_x_label=r'$p_{ES}$ in kW',
                        plot_z_label=r'$m_{Tank}$ in kg ',
                        plot_title=f'Variation Elektrolyseurleistung und Tank bei p_FC = {fixed_p_fc} kW',
                        exp_name=exp_name,
                                      file_name_prefix="EL_vs_Tank_Groupby_Tank_B")

# Elektrolyseur konstant, FC und Tank variabel

h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                        x_values=np.append(np.linspace(0, 1000, 11), [1500, 2000]), # Tank
                        z_values=[0, 100, 200, 500, 1000], # FC
                        key_path_x=['tank', 'fixed_capacity'],
                        key_path_z=['fuelcell', 'fixed_p'],
                        plot_x_label=r'$m_{Tank}$ in kg',
                        plot_z_label=r'$p_{FC}$ in kW ',
                        plot_title=f'Variation Brennstoffzellenleistung und Tank bei p_ES = {fixed_p_el} kW',
                                      exp_name=exp_name,
                                      file_name_prefix="Tank_vs_FC_Groupby_FC")

