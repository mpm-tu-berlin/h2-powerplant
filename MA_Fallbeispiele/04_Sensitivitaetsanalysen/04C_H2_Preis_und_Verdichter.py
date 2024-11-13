import copy
import json
import os
import numpy as np

import MA_Fallbeispiele.commonFunctions as h2ppcf

# =======================================================================================================================

datapath = os.path.join(os.path.dirname(__file__), "..", "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

# =======================================================================================================================

alle_ergebnisse = {}

with open(file_path) as user_file:
    parsed_json = json.load(user_file)

exp_name = "Exp_04C"


#h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
#                          x_values=np.linspace(1, 20, 10),
#                          key_path=['h2_price_per_kg_700bar'],
#                          plot_title='Gesamtkosten in Abh. vom Tankstellenpreis Wasserstoff (700 bar)',
#                          plot_x_label='H2 Preis in EUR/kg')

# Für die versch. Szenarien (mit Netzentgelte, ohne Aufschläge Strompreis, 10ct Aufschlag)

parsed_json_keine_st_ne = copy.deepcopy(parsed_json)
parsed_json_keine_st_ne["nur_beschaffungskosten"] = True

parsed_json_10ct_aufschlag = copy.deepcopy(parsed_json)
parsed_json_10ct_aufschlag["nur_beschaffungskosten"] = True
parsed_json_10ct_aufschlag['aufschlag_strom_manuell_ct'] = 10


the_scenarios = [parsed_json, parsed_json_keine_st_ne, parsed_json_10ct_aufschlag]
scenario_names = ['Basisszenario', 'Ohne St./Abg./Entgelte', 'Ohne Entgelte etc. - Manuell +10ct/kWh Aufschlag (immer)']

h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=parsed_json, original_folder_path=datapath,
                         x_values=np.linspace(2, 20, 19),
                          key_path=['h2_price_per_kg_700bar'],
                         plot_title=r'Gesamtkosten in Abh. vom H2-Preis (700 bar)',
                          plot_x_label='Preis in EUR/kg',
                                 exp_name=exp_name,
                                 file_name_prefix="TCO_nach_H2_Preis_Base")


h2ppcf.plot_sensitivity_multipe_scenarios(the_scenario_config_dicts=the_scenarios, scenario_labels=scenario_names,
                                          original_folder_path=datapath,
                                          x_values=np.linspace(1, 20, 20),
                                          key_path_x=['h2_price_per_kg_700bar'],
                                        plot_title='Gesamtkosten in Abh. vom Tankstellenpreis Wasserstoff (700 bar)',
                                          plot_x_label="H2 Preis in EUR/kg",
                                          hide_grid=False,
                                          exp_name=exp_name,
                                          file_name_prefix="TCO_nach_H2_Preis")

## ====
## Abweichend Kosten sensitivitität für 750 kW Elektrolyseur (für meinen Use Case hinreichend groß um schnell genug H2 für die FCEV zu erzeugen)
# ausserdem muss der HRS Verdichterinfra hinreichend gross sein, hier einfach mal random hoch genuge valuez
# el_750kw_json = copy.deepcopy(parsed_json)
# h2ppcf.set_nested_value(el_750kw_json, ['electrolyzer', 'fixed_p'], 750)
# h2ppcf.set_nested_value(el_750kw_json, ['HRS_Compressor', 'throughput_kg_per_hour'], 560)
# h2ppcf.set_nested_value(el_750kw_json, ['HRS_Compressor', 'hp_tank_capacity_kg'], 560)

# h2ppcf.calc_and_plot_sensitivity(the_parsed_config_json=el_750kw_json, original_folder_path=datapath,
#                          x_values=np.linspace(1, 30, 10),
#                           key_path=['h2_price_per_kg_700bar'],
#                          plot_title=r'Marktpreis Wasserstoff (700 bar) bei 750 kW $p_{EL}$ und hinreichend grosser HRS',
#                           plot_x_label='Preis in EUR/kg')


## ====

# 2. Wie groß muss diese verdichterinfra sein? => Durchsatz variieren evtl. sinnlos, wenn tank gross genug
# daher tankmenge anschauen
# calc_and_plot_sensitivity(the_parsed_config_json=el_750kw_json,
#                           x_values=np.linspace(30, 600, 10),
#                           key_path=['throughput_kg_per_hour'],
#                           plot_title=r'Size HRS Tank bei 750 kW $p_{EL}$ und hinreichend grossem Verdichterleistung kg/h',
#                           plot_x_label='Tank size kg')

# ====
