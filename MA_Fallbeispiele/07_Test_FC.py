'''
MA Chap. 6.4.5 (p. 143-145), Abb. 41:
Analyse einiger Kombinationen aus der Variation von elektr. und therm. Wirkungsgrad der Brennstoffzelle beim Fall
ohne FCEV bei verschiedenen Kostenszenarien
'''


import copy
import json
import os

from h2pp.optimizer import optimize_h2pp
import commonFunctions as h2ppcf

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie EUREF Duesseldorf")
file_path = os.path.join(datapath, "generated_ts_config_euref_dus.json")

# =======================================================================================================================

alle_ergebnisse = {}

with open(file_path) as user_file:
    parsed_json = json.load(user_file)

exp_name = "Exp_07"

parsed_json_keine_st_ne = copy.deepcopy(parsed_json)
parsed_json_keine_st_ne["nur_beschaffungskosten"] = True

parsed_json_10ct_aufschlag = copy.deepcopy(parsed_json)
parsed_json_10ct_aufschlag["nur_beschaffungskosten"] = True
parsed_json_10ct_aufschlag['aufschlag_strom_manuell_ct'] = 10

the_scenarios = [parsed_json, parsed_json_keine_st_ne, parsed_json_10ct_aufschlag]
scenario_names = ['Basisszenario', 'Ohne_Netzentgelte_usw', 'Manuell_10ct_Aufschlag']

####################################################################################################################

# STEUERUNG:::
#eta_el, eta_th = 0.5, 0.3
#selected_scen = parsed_json#_10ct_aufschlag

## Experimente: A) 0.5 und 0.3 für Wirkungsgrade; keine Netzentgelte.
#               B) 0.5 und 0.3 für Wirkungsgrade; MIT NE;
#               C) 0.7 und 0.3 MIT Netzentgelte.

####################################################################################################################

for eta_el, eta_th, selected_scen_str in [(0.5, 0.3, 'parsed_json_keine_st_ne'), (0.5, 0.3, 'parsed_json'), (0.7, 0.3, 'parsed_json')]:

    selected_scen = eval(selected_scen_str)
    subscen = copy.deepcopy(selected_scen)

    subscen['fuelcell']['efficiency_electric'] = eta_el
    subscen['fuelcell']['efficiency_thermal'] = eta_th

    ohne_fcevs = True

    if ohne_fcevs:
        # FCEV Flotte entfernen bei allen Wirkungsgradszenarien und erneut berechnen
        subscen['consumers'] = [consumer for consumer in subscen['consumers'] if
                                consumer['name'] != 'timeseries_fcev']

    file_path_out = os.path.join(datapath, '__temp_file_mod_eta_alle.json')  # may NOT exist or will be overwritten
    with open(file_path_out, "w") as user_file:
        json.dump(subscen, user_file, indent=4)

    tco_erg, figs = optimize_h2pp(file_path_out, mode="normal")
    print(tco_erg)


    h2ppcf.export_jahreszeiten_und_stacked_tco_plot(tco_erg, figs, exp_name, f"ohne_FCEV_{selected_scen_str}_eta_el_{eta_el}_und_th_{eta_th}")

