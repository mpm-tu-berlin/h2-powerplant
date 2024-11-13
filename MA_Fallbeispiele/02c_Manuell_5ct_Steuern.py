"""
Summe der Steuern/Umlagen/Netzentgelte/Abgaben testweise auf 5 ct/kWh setzen
"""

import json
import os

import commonFunctions as h2ppcf

datapath = os.path.join(os.path.dirname(__file__), "Fallstudie Exemplarisches Industrieareal")
file_path = os.path.join(datapath, "config_microgrid.json")

with open(file_path) as user_file:
    config_dict = json.load(user_file)

# Deaktiveren der Steuern, Abgaben, Netzentgelte und manuell die Stromkosten (nur Verkauf) um 5ct erhöhen
config_dict['nur_beschaffungskosten'] = True
config_dict['aufschlag_strom_manuell_ct'] = 5

file_path_out = os.path.join(datapath, '_temp_file_begrenzung_sb.json')  # may NOT exist or will be overwritten
with open(file_path_out, "w") as user_file:
    json.dump(config_dict, user_file, indent=4)

# Das ist unsere neue Base:
file_path = file_path_out


####################################################################

h2ppcf.fuenffach_analyse(datapath, file_path, "Exp_02C")
