"""
Optimierung in Grenzen für die Fallstudie EUREF Düsseldorf.
Hierbei unter Deaktivierung der Netzentgelte und Abgaben etc. (-> Testzwecke, siehe MA)
"""

import json
import os


import shutil
import tempfile
import warnings
import datetime

from h2pp.optimizer import optimize_h2pp
import commonFunctions as h2ppcf

# ==== EUREF mit Optimierung in Grenzen ====
# Nimmt die Originaldaten aber schmeißt die festen Leistungen und Kapazitäten raus und optimiert die. Analog für
# die Binärentscheidung ob komprimiert wird oder nicht

standard_value_throughput_50bar_compressor_kg_per_hour = 550
standard_value_density_prop_factor_h2_50bar_to_30bar = 1.32

with tempfile.TemporaryDirectory() as temp_dir:
    datapath = os.path.join(os.path.dirname(__file__), "Fallstudie EUREF Duesseldorf")
    common_data_path = os.path.join(os.path.dirname(__file__), "Common_Data")

    print(temp_dir)
    # Copy the config file and the contents of its folder to the temp dir
    # Destination may not exist or we get an error. either set dirs_exist_ok=True or set a non-existing subfolder..
    destination = shutil.copytree(datapath, os.path.join(temp_dir, 'subdirectory'))

    # We need the common data in the parent directory
    shutil.copytree(common_data_path, os.path.join(temp_dir, 'Common_Data'))

    print(destination)
    file_path = os.path.join(destination, "generated_ts_config_euref_dus.json")

    # Modify the config file
    with open(file_path) as user_file:
        parsed_json = json.load(user_file)

    # Netzentgelte deaktivieren?
    r = input("Netzentgelte/Abgaben deaktivieren? 1-ja, 2- nein: ")
    if r == "1":
        parsed_json['nur_beschaffungskosten'] = True
    elif r == "2":
        pass
    else:
        raise ValueError("Ungültige Eingabe")


    if 'electrolyzer' in parsed_json.keys():
        if 'fixed_p' in parsed_json['electrolyzer'].keys():
            del parsed_json['electrolyzer']['fixed_p']
        parsed_json['electrolyzer']['min_p'] = 0
        parsed_json['electrolyzer']['max_p'] = 5000

    if 'fuelcell' in parsed_json.keys():
        if 'fixed_p' in parsed_json['fuelcell'].keys():
            del parsed_json['fuelcell']['fixed_p']
        parsed_json['fuelcell']['min_p'] = 0
        parsed_json['fuelcell']['max_p'] = 500

    if 'tank' in parsed_json.keys():
        if 'fixed_capacity' in parsed_json['tank'].keys():
            del parsed_json['tank']['fixed_capacity']
        parsed_json['tank']['min_capacity'] = 0
        parsed_json['tank']['max_capacity'] = 1000

        if 'compress_before_storing' in parsed_json['tank'].keys():
            # delete the property
            del parsed_json['tank']['compress_before_storing']

        # check if the other two neccessary properties for 50 bar compression are present, raise warning if not and set them to the standard values specified in the beginning of this file, informing the users
        if 'density_prop_factor_h2_50bar_to_30bar' not in parsed_json['tank'].keys():
            warnings.warn(
                'density_prop_factor_h2_50bar_to_30bar not present in config file, setting to standard value')
            parsed_json['tank'][
                'density_prop_factor_h2_50bar_to_30bar'] = standard_value_density_prop_factor_h2_50bar_to_30bar
        if 'throughput_50bar_compressor_kg_per_hour' not in parsed_json['tank'].keys():
            warnings.warn(
                'throughput_50bar_compressor_kg_per_hour not present in config file, setting to standard value')
            parsed_json['tank'][
                'throughput_50bar_compressor_kg_per_hour'] = standard_value_throughput_50bar_compressor_kg_per_hour

    # Dump the modified config file
    with open(file_path, 'w') as user_file:
        json.dump(parsed_json, user_file)

    print(parsed_json)

    # According to https://www.researchgate.net/post/What_are_the_ways_population_size_in_genetic_algorithm,
    # some "experts" seem to set the population size to two times the number of variables. We have 4 paarams -> I choose 20 for safety
    # in Experiment 1B, we also had improvements near zero way before the end, converged already around/before the 40th gen. lets choose 50 here
    warnings.filterwarnings('ignore')
    print("Optimization Start: ", datetime.datetime.now())
    tco, figs = optimize_h2pp(file_path, mode="normal", # will use the default pop_size=50, n_gen=100
                              n_gen=50,
                              pop_size=30)
    print("Optimization Ende: ", datetime.datetime.now())

    exp_name = "Exp_03B"
    h2ppcf.export_jahreszeiten_und_stacked_tco_plot(tco, figs, exp_name, "H2PP_Math_Optimum")
    h2ppcf.multiple_tco_total_cost_comparison_export(exp_name, [tco], ["H2PP_Math_Optimum"])
    h2ppcf.multiple_tco_costs_and_revenue_bars_export(exp_name, [tco], ["H2PP_Math_Optimum"])

