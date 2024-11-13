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

exp_name = "Exp_04D"


# Note that the function will mutate the dict inplace, as dictionaries are passed by reference in Python by default
# For "Fast run", we only do the dict prep (Generation of time series etc.) only once (not affecting our altered properties anyway)
# Does not work or I will not able to really access the optimize_h2pp func which i NEED to simulate battery etc.
# prep_sim_config_dict(parsed_json=parsed_json, config_file_path=file_path)

parsed_json_keine_st_ne = copy.deepcopy(parsed_json)
parsed_json_keine_st_ne["nur_beschaffungskosten"] = True

parsed_json_10ct_aufschlag = copy.deepcopy(parsed_json)
parsed_json_10ct_aufschlag["nur_beschaffungskosten"] = True
parsed_json_10ct_aufschlag['aufschlag_strom_manuell_ct'] = 10


the_scenarios = [parsed_json, parsed_json_keine_st_ne, parsed_json_10ct_aufschlag]
scenario_names = ['Basisszenario', 'Ohne St./Abg./Entgelte', 'Ohne Entgelte etc. - Manuell +10ct/kWh Aufschlag (immer)']



####################################################################################################################

mit_vorverdichtung = copy.deepcopy(parsed_json)
mit_vorverdichtung["tank"]["compress_before_storing"] = True
mit_vorverdichtung["tank"]["hp_tank_capacity_kg"] = 56
mit_vorverdichtung["tank"]["throughput_50bar_compressor_kg_per_hour"] = 56

#h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=[parsed_json, mit_vorverdichtung], scenario_labels=['Ohne Vorverdichtung (38 bar)', 'Mit Vorverdichtung (50 bar)'],
#                                            x_values=np.linspace(0, 2000, 6), key_path_x=['tank', 'fixed_capacity'],
#                                            plot_title='Kosten bei variabler Tankkapazität', plot_x_label="$m_{Tank} in kg bei äquiv. 38-bar-Tank$")

mit_vorverdichtung_keine_st_ne = copy.deepcopy(parsed_json)
mit_vorverdichtung_keine_st_ne["nur_beschaffungskosten"] = True

h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=[parsed_json_keine_st_ne, mit_vorverdichtung_keine_st_ne],
                                            original_folder_path=datapath,
                                          scenario_labels=['Ohne Vorverdichtung (38 bar)', 'Mit Vorverdichtung (50 bar)'],
                                            x_values=np.linspace(0, 2000, 9), key_path_x=['tank', 'fixed_capacity'],
                                            plot_title='Kosten bei variabler Tankkapazität - ohne Steuern/Abgaben/etc.', plot_x_label="$m_{Tank} in kg bei äquiv. 38-bar-Tank$",
                                          exp_name=exp_name,
                                          file_name_prefix="Vorverdichtung_50bar_vs_38bar")

####################################################################################################################


h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=the_scenarios, scenario_labels=scenario_names,
                                          original_folder_path=datapath,
                                          x_values=np.linspace(0, 1200, 9),
                                          key_path_x=['fuelcell', 'fixed_p'],
                                        plot_title='Kosten bei variabler Brennstoffzellen(ausgangs-)leistung', plot_x_label="$p_{FC}$ in kW",
                                          hide_grid=False,
                                          exp_name=exp_name,
                                          file_name_prefix="FC_0_1200_kW")


h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=the_scenarios, scenario_labels=scenario_names,
                                            original_folder_path=datapath,
                                          x_values=np.linspace(0, 2000, 9),
                                          key_path_x=['tank', 'fixed_capacity'],
                                        plot_title='Kosten bei variabler Tankkapazität', plot_x_label="$m_{Tank}$ in kg",
                                          hide_grid=False,
                                          exp_name=exp_name,
                                          file_name_prefix="Tank_0_2000_kg")

####################################################################################################################




h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=parsed_json_keine_st_ne, original_folder_path=datapath,
                      x_values=np.linspace(0.1, 1.0, 17),
                      key_path=['electrolyzer', 'efficiency'],
                      plot_title=f'Variation Elektrolyseur-Wirkungsgrad ohne Steuern/Abgaben/Entgelte',
                      plot_x_label=r'$\eta_{ES}$',
                      exp_name=exp_name,
                                 file_name_prefix="Wirkungsgrad_Elektrolyseur")

h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=parsed_json_keine_st_ne, original_folder_path=datapath,
                      x_values=np.linspace(0.1, 0.673, 10),
                      key_path=['fuelcell', 'efficiency_electric'],
                      plot_title=f'Variation elektr. Wirkungsgrad Brennstoffzelle ohne Steuern/Abgaben/Entgelte',
                      plot_x_label=r'$\eta_{FC}$',
                    exp_name=exp_name,
                                 file_name_prefix="Wirkungsgrad_FC")


####################################################################################################################

# Elektrolyseur Wirkungsgrade
for i, scenario in enumerate(the_scenarios):
    h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=the_scenarios[i], original_folder_path=datapath,
                                         x_values=np.linspace(0.6, 1.0, 10), # TODO evtl auch schon bei 0.4 starten? Sieht man das Konvergeznzverhalten nochmal schöner, aber in der realität haben vermutlich nicht so hohe wirkungsgrade.
                                         z_values=[0.425, 0.55, 0.673], #[100, 228, 335],
                                         key_path_x=['electrolyzer', 'efficiency'],
                                         key_path_z=['fuelcell', 'efficiency_electric'],
                                         plot_title=f'TCO vs Wirkungsgrade der Wandler - {scenario_names[i]}, bei eta_fc_th=0.327',
                                         plot_x_label=r'$\eta_{ES}$',
                                         plot_z_label=r'$\eta_{FC, el} = $',
                                          exp_name=exp_name,
                                          file_name_prefix=f"Wirkungsgrade_ES_FC_{i}")


for i, scenario in enumerate(the_scenarios):
    h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=scenario, original_folder_path=datapath,
                          x_values=np.linspace(150, 2000, 10),
                          key_path=['electrolyzer', 'fixed_p'],
                          plot_title=f'Variation Elektrolyseurleistung - {scenario_names[i]}',
                          plot_x_label=r'$p_{ES}$ in kW',
                                     exp_name=exp_name,
                                     file_name_prefix=f"ES_{i}_150_2000kW")

    h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=scenario, original_folder_path=datapath,
                          x_values=np.linspace(50, 500, 8),
                          key_path=['electrolyzer', 'fixed_p'],
                          plot_title=f'Variation Elektrolyseurleistung - {scenario_names[i]}',
                          plot_x_label=r'$p_{ES}$ in kW',
                                     exp_name=exp_name,
                                     file_name_prefix=f"ES_{i}_50_500kW")

#h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=scenario,   original_folder_path=datapath,
#                      x_values=np.linspace(150, 2000, 10),
#                      key_path=['electrolyzer', 'fixed_p'],
#                      plot_title=f'Variation Elektrolyseurleistung - {scenario_names[i]}',
#                      plot_x_label=r'$p_{ES} in kW$',
#                      z_type="dictionaries")

#for i, scenario in enumerate(the_scenarios):
#    h2ppcf.calc_and_plot_pair_sensitivity(the_parsed_config_json=None,
#                                             x_values=np.linspace(0, 500, 5), # TODO evtl auch schon bei 0.4 starten? Sieht man das Konvergeznzverhalten nochmal schöner, aber in der realität haben vermutlich nicht so hohe wirkungsgrade.
#                                             z_values=the_scenarios,
#                                             key_path_x=['fuelcell', 'fixed_p'],
#                                             key_path_z=None,
#                                             plot_title=f' - {scenario_names[i]}, bei eta_fc_th=0.327',
#                                             plot_x_label=r'$\eta_{ES}$',
#
