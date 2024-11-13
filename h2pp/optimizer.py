"""

referenced sources used below for TCO values:
Atabay & Devrim 2024 -> doi: 10.1016/j.ijhydene.2024.07.166. url: https://www.sciencedirect.com/science/article/pii/S0360319924028404
Accelera: Final_FuelCellPowerSystems-SpecSheet_March24.pdf. März 2024. url: https://www.accelerazero.com/sites/default/files/2024-03/Final_ FuelCellPowerSystems-SpecSheet_March24.pdf.

"""

import json
import math
import os
import warnings
from dataclasses import dataclass
from typing import Dict, Literal

import numpy as np
from oemof import solph
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.variable import Binary
from pymoo.core.mixed import MixedVariableGA
from pymoo.core.variable import Real
from pymoo.optimize import minimize

import h2pp.generators
from h2pp import helperFunctions, strompreise, tco
from h2pp.generators import Jahreszeit
from h2pp.helperFunctions import EvaluationResult
from h2pp.simulation import run_simulation
import plotly.graph_objects as go


@dataclass(
    frozen=True)  # we need frozen=true to avoid the objects being modified, which seems to be required for the optimization algo (at least later for the paralellization)
class CapexParameters:
    # if we are evaluating a regular scenario, all parameters except c_battery_refcase_only and battery_lifetime_years should be set.
    # if we are evaluating the reference case for battery storage, all parameters except c_battery_refcase and battery_lifetime_years should be None.
    cost_data_identifier: str
    p_el: float
    p_fc: float
    m_tank: float
    c_battery_refcase_only: float | None  # Only to be set in reference case for battery.
    battery_lifetime_years: float | None  # Only to be set in reference case for battery.
    m_tank_HP: float


@dataclass(
    frozen=True)  # we need frozen=true to avoid the objects being modified, which seems to be required for the optimization algo (at least later for the paralellization)
class OpexParameters:
    # Achtung: Die Kosten sind POSITIVE Werte, die Einnahmen NEGATIVE Werte
    total_cost_electricity_buy: float
    total_cost_h2_buy: float
    total_revenue_heat_sell: float
    total_revenue_electricity_sell: float


def calculate_tco(capex_params: CapexParameters, opex_params: Dict[int, OpexParameters]) -> tco.TCO:

    """
    Calculates the total cost of ownership for the given Parameter set for the Micro Grid and corresp. simulation results.

    Also, a different cost data can be used if the cost_data_identifier inside eval_params_base is set to one of
    the values far below near the end of this function

    @return: An h2pp.TCO Object containing the cost data.
    """

    # TODO: Suggestions for the future:
    #   - berücksichtigen, dass evtl. verschiedene Typen von elektrolyseuren verschiedene Kostenwerte brauchen.
    #   - Möglichkeit es flexibel "easy" anzupassen, py/json file oder sowas.
    #   - Wallbox kosten für Battery Ref case (sollte nicht viel sein, max 8000 EUR pro Wallbox? sind bei 20 Wallboxen nur 160k EUR, also vergleichsweise nicht so viel)

    exchange_rate_usd_to_eur = 0.90  # Average exchange rate between 2020-08 and 2024-07

    costData_Standard = {
        'CAPEX':
            {
                'Elektrolyseur':
                    {
                        # Price development more as an assumption loosely based on some studies that see a huge decrease in near future, see Thesis JC
                        'escalation':
                            dict([(year, -0.05) for year in range(2025, 2035)]
                                 + [(year, -0.02) for year in range(2035, 2045)]
                                 + [(year, -0.01) for year in range(2045, 2056)]),
                        'escalation_type': 'compound',
                        'unit_cost': 2000,  # Atabay & Devrim 2024, Table 2
                        'base_year': 2025,
                        'quantity': 0 if capex_params.p_el is None else capex_params.p_el,  # kW
                        'depreciation_period': 20,  # Enapter Quelle bzw. Atabay & Devrim
                        'salvage_value': 'linear'
                    },
                'Brennstoffzelle':
                    {
                        # Price development more as an assumption loosely based on some studies that see a huge decrease in near future, see Thesis JC
                        'escalation':
                            dict([(year, -0.05) for year in range(2025, 2035)]
                                 + [(year, -0.02) for year in range(2035, 2045)]
                                 + [(year, -0.01) for year in range(2045, 2056)]),
                        'escalation_type': 'compound',
                        'unit_cost': 1000,
                        'base_year': 2025,
                        'quantity': 0 if capex_params.p_fc is None else capex_params.p_fc,  # kW
                        'depreciation_period': 20,  # Accelera Wert 03.2024
                        'salvage_value': 'linear'
                    },
                'Tank_LP':  # the 30 or 50 bar (Type 1) low pressure tank
                    {
                        'escalation':
                            dict([(year, -0.05) for year in range(2025, 2035)]
                                 + [(year, -0.02) for year in range(2035, 2045)]
                                 + [(year, -0.01) for year in range(2045, 2056)]),
                        'escalation_type': 'compound',
                        'unit_cost': 632,
                        # Atabay & Devrim 2024 ("Storage up to 50bar). Here it is a bit unclear how to handle the 30vs50bar thing. Technically, if we compare the 50bar tank to the 30bar one; with 50bar we would need a smaller tank for the same amount of kg H2.
                        # We use this value always with the 30bar kg value. if i would base the calculations for 50bar on EUR/kg, the higher-pressured tank would always lose as it is not only more expensive but also we may need additional compression power (30->50->30) in storing
                        # a value based on EUR/m^3 would be nice
                        'base_year': 2025,
                        'quantity': 0 if capex_params.m_tank is None else capex_params.m_tank, # €/kg
                        'depreciation_period': 20,  # Atabay & Devrim 2024
                        'salvage_value': 'linear'
                    },

            },
        'OPEX':
            {

                'Electricity_Buy':
                    {
                        'escalation':
                            dict([(year, opex_params[year].total_cost_electricity_buy) for year
                                  in range(2025, 2056)]),
                        # hier energy per year kWh/a (siehe "Hack" in der TCO.py Calculation)
                        'escalation_type': 'custom_per_year_jc',  # siehe "Hack" in der TCO.py Calculation
                        'unit_cost': 0,  # siehe "Hack" in der TCO.py Calculation
                        'base_year': 2025,
                        'quantity': 1  # Siehe "Hack": Gesamte Kosten bereits in dem Dict bei "escalation" eingetragen, MUSS daher auf 1 gesetzt werden da die Werte aus escalation hiermit multipliziert werden.
                    },

                'H2_Buy':
                    {
                        'escalation':
                            dict([(year, opex_params[year].total_cost_h2_buy) for year
                                  in range(2025, 2056)]),
                        # hier energy per year kWh/a (siehe "Hack" in der TCO.py Calculation)
                        'escalation_type': 'custom_per_year_jc',  # siehe "Hack" in der TCO.py Calculation
                        'unit_cost': 0,  # siehe "Hack" in der TCO.py Calculation
                        'base_year': 2025,
                        'quantity': 1  # analog zur Überlegung bei 'Electricity_Buy'
                    },

                'Heat_Savings':
                    {
                        'escalation':
                            dict([(year, opex_params[year].total_revenue_heat_sell) for year
                                  in range(2025, 2056)]),
                        # hier energy per year kWh/a (siehe "Hack" in der TCO.py Calculation)
                        'escalation_type': 'custom_per_year_jc',  # siehe "Hack" in der TCO.py Calculation
                        'unit_cost': 0,  # siehe "Hack" in der TCO.py Calculation
                        'base_year': 2025,
                        'quantity': 1  # analog zur Überlegung bei 'Electricity_Buy'
                    },

                'Electricity_Sell':
                    {
                        'escalation':
                            dict([(year, opex_params[year].total_revenue_electricity_sell) for year
                                  in range(2025, 2056)]),
                        # hier energy per year kWh/a (siehe "Hack" in der TCO.py Calculation)
                        'escalation_type': 'custom_per_year_jc',  # siehe "Hack" in der TCO.py Calculation
                        'unit_cost': 0,  # siehe "Hack" in der TCO.py Calculation
                        'base_year': 2025,
                        'quantity': 1  # analog zur Überlegung bei 'Electricity_Buy'
                    },

            }
    }


    # todo vlt in kleine Funktion auslagern die ein OPEX basierend auf CAPEX + % erstellt (hier viel "duplicate code" sonst).

    # add percentage for operation & Mainentenance OPEX costs based on % CAPEX costs; so also with same escalation and quantities

    # values based on (Atabay & Devrim 2024, Table 2) if not specified otherwise
    costData_Standard['OPEX']['OMC_Elektrolyseur'] = costData_Standard['CAPEX']['Elektrolyseur'].copy()
    costData_Standard['OPEX']['OMC_Elektrolyseur']['unit_cost'] *= 0.02  # 2% of CAPEX costs (Atabay & Devrim 2024)

    costData_Standard['OPEX']['OMC_Brennstoffzelle'] = costData_Standard['CAPEX']['Brennstoffzelle'].copy()
    costData_Standard['OPEX']['OMC_Brennstoffzelle'][
        'unit_cost'] *= 0.02  # Annahme identische OMC kosten (2% of CAPEX costs) wie beim Elektrolyseur (ohne Quelle)

    costData_Standard['OPEX']['OMC_Tank_LP'] = costData_Standard['CAPEX']['Tank_LP'].copy()
    costData_Standard['OPEX']['OMC_Tank_LP'][
        'unit_cost'] *= 0.01  # (should be!) 1% of CAPEX costs (cf. Atabay & Devrim 2024, Table 2)

    # find out if we need the hydrogen refueling station or not:
    # as it is only needed in the "normal case" (no battery / status quo reference case)
    # If we neither have a electrolyzer nor a tank, we do not need the hydrogen refueling station as no hydrogen is produced or stored
    if capex_params.p_el is None and capex_params.m_tank is None:
        pass
    else:
        costData_Standard['CAPEX']['Tank_HP'] = {

            # the 700 bar (Type 4) high pressure tank (respective, representing the three tanks for the three stages)

            'escalation':
                dict([(year, -0.05) for year in range(2025, 2035)]
                     + [(year, -0.02) for year in range(2035, 2045)]
                     + [(year, -0.01) for year in range(2045, 2056)]),
            'escalation_type': 'compound',
            'unit_cost': 1144,
            # Atabay & Devrim 2024 ("Storage (1000 bar)"). However, might be a bit less now, as the referenced price values in the 2024 source are already from 2017. Other sources state e.g. Urs 2023: 700 USD/kg
            'base_year': 2025,
            'quantity': capex_params.m_tank_HP,
            'depreciation_period': 20,  # Atabay & Devrim 2024
            'salvage_value': 'linear'
        }

        # Folgende Werte für Compressor, Cooling, Dispenser irgendwie fix bei Atabay & Devrim, ggfs. muss man hier nochmal schauen ob deren Auslegungsfall zu unseren Anforderungen passt.

        costData_Standard['CAPEX']['Compressor'] = {
            'escalation':
                dict([(year, 0.0) for year in range(2025, 2056)]),  # here, I have no data
            'escalation_type': 'compound',
            'unit_cost': 394398,  # Atabay & Devrim 2024, Table 2
            'base_year': 2025,
            'quantity': 1,
            'depreciation_period': 20,  # Atabay & Devrim 2024, Table 2
            'salvage_value': 'linear'
        }

        costData_Standard['CAPEX']['Cooling'] = {
            'escalation':
                dict([(year, 0.0) for year in range(2025, 2056)]),  # here, I have no data
            'escalation_type': 'compound',
            'unit_cost': 140000,  # Atabay & Devrim 2024, Table 2
            'base_year': 2025,
            'quantity': 1,
            'depreciation_period': 20,  # Atabay & Devrim 2024, Table 2
            'salvage_value': 'linear'
        }

        costData_Standard['CAPEX']['Dispenser'] = {
            'escalation':
                dict([(year, 0.0) for year in range(2025, 2056)]),  # here, I have no data
            'escalation_type': 'compound',
            'unit_cost': 107000,  # Atabay & Devrim 2024, Table 2
            'base_year': 2025,
            'quantity': 1,
            'depreciation_period': 20,  # Atabay & Devrim 2024, Table 2
            'salvage_value': 'linear'
        }

        costData_Standard['OPEX']['OMC_Tank_HP'] = costData_Standard['CAPEX']['Tank_HP'].copy()
        costData_Standard['OPEX']['OMC_Tank_HP'][
            'unit_cost'] *= 0.01  # (should be!) 1% of CAPEX costs (cf. Atabay & Devrim 2024, Table 2)

        costData_Standard['OPEX']['OMC_Compressor'] = costData_Standard['CAPEX']['Compressor'].copy()
        costData_Standard['OPEX']['OMC_Compressor']['unit_cost'] *= 0.08

        costData_Standard['OPEX']['OMC_Cooling'] = costData_Standard['CAPEX']['Cooling'].copy()
        costData_Standard['OPEX']['OMC_Cooling']['unit_cost'] *= 0.03

        costData_Standard['OPEX']['OMC_Dispenser'] = costData_Standard['CAPEX']['Dispenser'].copy()
        costData_Standard['OPEX']['OMC_Dispenser']['unit_cost'] *= 0.03

    # For all our opex values we delete the depreciation period and salvage value as they are not needed for the TCO
    # calculation (only for convenience! not necessarily required, as the TCO code ignores them anyway).
    # they are the results from copying the CAPEX values, which have these values set

    for key in costData_Standard['OPEX'].keys():
        for subkey in ['depreciation_period', 'salvage_value']:
            if subkey in costData_Standard['OPEX'][key].keys():
                del costData_Standard['OPEX'][key][subkey]

    # Add battery only to TCO if we are in the reference case for battery storage; and remove Electrolizer, Fuel Cell,
    # and Low Pressure Tank at the same time
    if capex_params.c_battery_refcase_only is not None:
        costData_Standard['CAPEX']['Batterie'] = {
            # Price development more as an assumption loosely based on some studies that see a huge decrease in near future, see Thesis JC
            'escalation':
                dict([(year, -0.05) for year in range(2025, 2035)]
                     + [(year, -0.02) for year in range(2035, 2045)]
                     + [(year, -0.01) for year in range(2045, 2056)]),
            'escalation_type': 'compound',  # compound = from previous to current year
            'unit_cost': 150,
            'base_year': 2025,
            'quantity': 0 if capex_params.c_battery_refcase_only is None else capex_params.c_battery_refcase_only,
            'depreciation_period': max(1, math.floor(
                capex_params.battery_lifetime_years)) if capex_params.c_battery_refcase_only is not None else 30,
            'salvage_value': 'linear'
        }

        # remove the other components from the cost data
        for key in ['Elektrolyseur', 'Brennstoffzelle', 'Tank_LP']:
            del costData_Standard['CAPEX'][key]

        # ====

    # This overview dict creation is especially needed for some plots later
    overview_H2PP = tco.create_h2pp_overview_dict(costData_Standard)


    tco_parameters_dict = {
        'start_year': 2025,
        'project_duration': 30,
        'i_discount': 0.0201,
        'repeat_procurements': True,
        'use_salvage_value': True,
        'i_capital': 0,
        'annualise': False
    }

    # Select the cost data used for calculation based on given parameter / modify dict to these changes
    cost_data_identifier = capex_params.cost_data_identifier

    if cost_data_identifier == 'STANDARD':
        pass

    # TODO these are just unused examples to demonstrate how to use a cost_data_identifier.
    #   Note that the OPEX of OMC values etc. might need to also get refreshed if we alter the CAPEX values (otherwise,
    #   it would not represent the correct % CAPEX cost value)

    elif cost_data_identifier == 'GUENSTIGER_ELEKTROLYSEUR':
        costData_Standard['CAPEX']['Elektrolyseur']['unit_cost'] = 1000  # € / kW

    elif cost_data_identifier == 'TEURE_BRENNSTOFFZELLE':
        costData_Standard['CAPEX']['Brennstoffzelle']['unit_cost'] = 2000  # € / kW

    else:
        print("Selected TCO Cost Data Object not known! Proceeding with standard.. [Optimierung TCO]")

    TCO_Obj = tco.TCO(costData_Standard,
                      start_year=tco_parameters_dict["start_year"],
                      project_duration=tco_parameters_dict["project_duration"],
                      i_discount=tco_parameters_dict["i_discount"],
                      repeat_procurements=tco_parameters_dict["repeat_procurements"],
                      use_salvage_value=tco_parameters_dict["use_salvage_value"],
                      i_capital=tco_parameters_dict["i_capital"],
                      annualise=tco_parameters_dict["annualise"],
                      overview_dict=overview_H2PP)

    return TCO_Obj


#TODO: Ggfs. um Parallelization erweitern.
class H2PP_Standard_MixedVariableProblem(ElementwiseProblem):

    def __init__(self, sim_config_dict, *args, **kwargs):
        # Tipps/Anleitung siehe https://pymoo.org/customization/mixed.html
        # Genereller Aufbau der Vars Variable für pymoo (Bsp.):
        # vars = {
        #
        #         # "b": Binary(),
        #         # "x": Choice(options=["nothing", "multiply"]),
        #         # "y": Integer(bounds=(0, 2)),
        #         # "z": Real(bounds=(0, 5)),
        #         # }

        vars = {}

        # Ermittlung der Variablen, die in der Optimierung berücksichtigt werden sollen
        # => ist bspw. die Elektrolyseurleistung in der JSON als fixed_p angegeben, so muss ihr Wert nicht optimiert werden

        if "tank" in sim_config_dict.keys():
            if "compress_before_storing" not in sim_config_dict["tank"].keys():
                # If no explicit value for compress_before_storing is given, then it must be optimized
                vars["compress_before_storing"] = Binary()

            if "min_capacity" in sim_config_dict["tank"].keys() and "max_capacity" in sim_config_dict[
                "tank"].keys() and "fixed_capacity" not in sim_config_dict["tank"].keys():
                # If min_capacity and max_capacity are given, then the tank capacity must be optimized
                vars["m_tank"] = Real(
                    bounds=(sim_config_dict["tank"]["min_capacity"], sim_config_dict["tank"]["max_capacity"]))

            elif ("fixed_capacity" in sim_config_dict["tank"].keys()) and (
                    "min_capacity" not in sim_config_dict["tank"].keys()) and (
                    "max_capacity" not in sim_config_dict["tank"].keys()):
                # Valid Config (fixed_capacity is given)
                pass

            else:
                raise ValueError(
                    "Invalid capacity configuration in the config file. Either (min_capacity AND max_capacity) must be given, OR fixed_capacity must be given.")

        # Das config dict muss in der Klasse als Attribut gespeichert werden, um es in der _evaluate Methode nutzen zu können
        self.sim_config_dict = sim_config_dict

        # Wenn Dicts für Elektrolyseur resp. Brennstoffzelle vorhanden sind, dann sollen diese nicht "abgeschaltet" werden

        if "electrolyzer" in sim_config_dict.keys():
            # Do not "turn off" electrolyzer if it is in the config file; add the variable to the optimization problem

            if "min_p" in sim_config_dict["electrolyzer"].keys() and "max_p" in sim_config_dict[
                "electrolyzer"].keys() and "fixed_p" not in sim_config_dict["electrolyzer"].keys():
                vars["p_el"] = Real(bounds=(
                    sim_config_dict["electrolyzer"]["min_p"], sim_config_dict["electrolyzer"]["max_p"]))  # in kW

            elif ("fixed_p" in sim_config_dict["electrolyzer"].keys()) and (
                    "min_p" not in sim_config_dict["electrolyzer"].keys()) and (
                    "max_p" not in sim_config_dict["electrolyzer"].keys()):
                # Valid Config (fixed_p is given)
                pass

            else:
                raise ValueError(
                    "Invalid electrolyzer power configuration in the config file. Either (min_p AND max_p) must be given, OR fixed_p must be given.")

        if "fuelcell" in sim_config_dict.keys():
            # Do not "turn off" electrolyzer if it is in the config file; add the variable to the optimization problem

            if "min_p" in sim_config_dict["fuelcell"].keys() and "max_p" in sim_config_dict[
                "fuelcell"].keys() and "fixed_p" not in sim_config_dict["fuelcell"].keys():
                vars["p_fc"] = Real(
                    bounds=(sim_config_dict["fuelcell"]["min_p"], sim_config_dict["fuelcell"]["max_p"]))  # in kW

            elif ("fixed_p" in sim_config_dict["fuelcell"].keys()) and (
                    "min_p" not in sim_config_dict["fuelcell"].keys()) and (
                    "max_p" not in sim_config_dict["fuelcell"].keys()):
                # Valid Config (fixed_p is given)
                pass

            else:
                raise ValueError(
                    "Invalid fuelcell power configuration in the config file. Either (min_p AND max_p) must be given, OR fixed_p must be given.")

        super().__init__(vars=vars, n_obj=1, *args, **kwargs)

    def _retrieve_parameter_set(self, X):
        if "p_el" in X.keys():
            # Variable Power for Electrolyzer
            p_el = X["p_el"]

        elif "electrolyzer" in self.sim_config_dict.keys():
            # Fixed Power for Electrolyzer (Electrolyzer not turned off and no variable power value was specified)
            p_el = self.sim_config_dict["electrolyzer"]["fixed_p"]
        else:
            p_el = None

        if "p_fc" in X.keys():
            # Variable Power for Fuel Cell
            p_fc = X["p_fc"]
        elif "fuelcell" in self.sim_config_dict.keys():
            # Fixed Power for Fuel Cell (Fuel Cell not turned off and no variable power value was specified)
            p_fc = self.sim_config_dict["fuelcell"]["fixed_p"]
        else:
            p_fc = None

        if "m_tank" in X.keys():
            m_tank = X["m_tank"]
        elif "tank" in self.sim_config_dict.keys():
            m_tank = self.sim_config_dict["tank"]["fixed_capacity"]
        else:
            m_tank = None

        if m_tank is not None:
            if "compress_before_storing" in X.keys():
                compress_before_storing = X["compress_before_storing"]
            elif "compress_before_storing" in self.sim_config_dict["tank"].keys():
                compress_before_storing = self.sim_config_dict["tank"]["compress_before_storing"]
            else:
                raise ValueError(
                    "compress_before_storing must be specified in the config file or as an optimization variable.")
        else:
            compress_before_storing = False

        return {
            "p_el": p_el,
            "p_fc": p_fc,
            "m_tank": m_tank,
            "compress_before_storing": compress_before_storing
        }

    def _evaluate(self, X, out, *args, **kwargs):
        p_el = self._retrieve_parameter_set(X)["p_el"]
        p_fc = self._retrieve_parameter_set(X)["p_fc"]
        m_tank = self._retrieve_parameter_set(X)["m_tank"]
        compress_before_storing = self._retrieve_parameter_set(X)["compress_before_storing"]

        tco_obj = eval_scenario(p_el, p_fc, m_tank, compress_before_storing, c_battery=None,
                                sim_config_dict=self.sim_config_dict).tco

        out["F"] = tco_obj.npv_total


def get_optimum_for_battery_refcase_only(sim_config_dict, **kwargs) -> (float, tco.TCO):
    # As the battery ref case only has the battery capacity as a variable, we just take some values in the given interval,
    # evaluate them and return the best one.

    # TODO evtl. allow more flexibility over the linspace size (currently always 10)

    if "battery" not in sim_config_dict.keys():
        raise ValueError("Battery configuration missing in the config file.")

    if ("fixed_capacity" in sim_config_dict["battery"].keys() and "min_capacity" in sim_config_dict[
        "battery"].keys()) or (
            "fixed_capacity" in sim_config_dict["battery"].keys() and "max_capacity" in sim_config_dict[
        "battery"].keys()):
        raise ValueError(
            "Invalid battery configuration in the config file. Either fixed_capacity must be given, OR min_capacity AND max_capacity must be given.")

    if not ("fixed_capacity" in sim_config_dict["battery"].keys()) and not (
            "min_capacity" in sim_config_dict["battery"].keys() and "max_capacity" in sim_config_dict[
        "battery"].keys()):
        raise ValueError(
            "Invalid battery configuration in the config file. Either fixed_capacity must be given, OR min_capacity AND max_capacity must be given.")

    if "fixed_capacity" in sim_config_dict["battery"].keys():
        capacities_to_evaluate = [sim_config_dict["battery"]["fixed_capacity"]]
    else:
        capacities_to_evaluate = np.linspace(sim_config_dict["battery"]["min_capacity"],
                                             sim_config_dict["battery"]["max_capacity"], 10)

    best_npv = np.inf  # Storing the current best found npv value
    best_eval_res = None  # TCO object corresponding to the best found npv value
    best_capacity = None  # Capacity corresponding to the best found npv value
    for capacity in capacities_to_evaluate:
        eval_res = eval_scenario(p_el=None, p_fc=None, m_tank=None, compress_before_storing=False, c_battery=capacity,
                                sim_config_dict=sim_config_dict, **kwargs)
        tco_obj = eval_res.tco
        print(capacity, tco_obj.npv_total)

        if tco_obj.npv_total < best_npv:
            best_npv = tco_obj.npv_total
            best_capacity = capacity
            best_eval_res = eval_res

    print(best_capacity, best_eval_res.tco.npv_total)

    return best_capacity, best_eval_res


def eval_scenario(p_el, p_fc, m_tank, compress_before_storing, c_battery, sim_config_dict, verbose=False) -> EvaluationResult:
    # Wieso wird die config_file_path übergeben und nicht das JSON selbst? => brauchen ggfs. relative Pfadangaben die in der JSON spezifiert sind, müssen also wissen wo das Root ist

    dict_sim_opex_results: Dict[
        int, OpexParameters] = {}  # dict with the years as the keys and the OpexParameters as the values

    # For each year: Sommer, Winter, Übergang berechnet und zusammengezählt
    total_cost_electricity_buy_spot_sum_only = 0
    total_cost_h2_buy = 0
    total_revenue_heat_sell = 0
    total_revenue_electricity_sell = 0
    perc_deg_battery = 0

    max_peak_power_ac_grid = 0
    total_energy_bought_year_kWh = 0
    total_cost_electricity_buy = 0

    for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
        sim_results = run_simulation(sim_config_dict=sim_config_dict, jahreszeit=jahreszeit, p_el=p_el, p_fc=p_fc,
                                     m_tank=m_tank, compress_before_storing=compress_before_storing,
                                     c_battery=c_battery, verbose=verbose)

        # Zuordnung der Anzahl Tage derzeit statisch basierend auf der Zuteilung wie ich es überall anders auch habe.
        months = h2pp.generators.typical_months(jahreszeit)
        num_weeks = helperFunctions.sum_days_in_months(months) / 7

        # Bestimmung der bezogenen Energiemengen aus dem Simulationsresultat; Skalierung auf den Zeitraum und Berechnung Energiekosten
        # Für Stromkosten Kauf hier zunächst nur Anteil Börsenpreis addiert, Rest wird unten addiert
        electricity_buy_sequence_kW = solph.views.node(sim_results["sim_results"], 's_el_grid_buy')["sequences"].values[:-2, 0]
        total_energy_bought_year_kWh += sum(electricity_buy_sequence_kW) * (sim_config_dict["base_sim_interval"] / 60) * num_weeks # kWh
        max_peak_power_ac_grid = max(max_peak_power_ac_grid, max(electricity_buy_sequence_kW)) # Peak für Arbeits- und Leistungspreis bestimmen

        total_cost_electricity_buy_spot_sum_only += sim_results["el_grid_source_total_cost_spot_price_only"] * num_weeks
        total_cost_h2_buy += sim_results["h2_grid_source_total_cost"] * num_weeks
        total_revenue_heat_sell += sim_results["heat_grid_sink_total_cost"] * num_weeks
        total_revenue_electricity_sell += sim_results["el_grid_sink_total_cost"] * num_weeks

        # Abnutzung der Batterie in dieser Jahreszeit via Rainflow-Algorithmus
        if c_battery is not None:
            verlauf_soc_battery = sim_results["battery_sequence_soc"]
            perc_deg_battery += helperFunctions.get_lfp_battery_percent_degradation(verlauf_soc_battery) * num_weeks

    if perc_deg_battery < 0.0001:
        lifetime_battery = 1000  # arbitrarily high value to avoid division by zero
    else:
        lifetime_battery = 1 / perc_deg_battery

    if c_battery is not None:
        if verbose:
            print(lifetime_battery)

    # Berechnung der tatsächlichen Steuern, Umlagen, Netzentgelte:

    steuern_umlagen_real = h2pp.strompreise.stromkosten_2024(jahresverbrauch_in_kWh=total_energy_bought_year_kWh,
                                                             peak_leistung_in_kW=max_peak_power_ac_grid,
                                                             spannungsebene=h2pp.strompreise.Spannungsebene[
                                                  sim_config_dict["spannungsebene"]],
                                                             ort=sim_config_dict["ort"],
                                                             kat_konzession=sim_config_dict["kat_konzession"]
                                                             )

    # Diese Kostenanteile werden je nachdem addiert, ob sie laut Konfigurationsdatei zu berücksichtigen sind oder nicht
    if "nur_beschaffungskosten" in sim_config_dict:
        if sim_config_dict["nur_beschaffungskosten"]:
            warnings.warn("Netzentgelte, Umlagen usw werden ignoriert!")
            steuern_umlagen_real = 0.0

    if "aufschlag_strom_manuell_ct" in sim_config_dict:
        # Manueller Wert für die Summe aus Steuern, Abgaben, Umlagen, Netzentgelte etc. (alles außer Börsenpreis)
        steuern_umlagen_real = sim_config_dict["aufschlag_strom_manuell_ct"] / 100

    if verbose:
        print("Tatsächliche Steuern & Umlagen: ", steuern_umlagen_real)
        print("Tatsächlicher JahresBEZUG: ", total_energy_bought_year_kWh)
        print("Echter Peak: ", max_peak_power_ac_grid)

    total_cost_electricity_buy += total_cost_electricity_buy_spot_sum_only + total_energy_bought_year_kWh * steuern_umlagen_real

    # Aufschläge Leistungspreis
    lpr = h2pp.strompreise.leistungspreis(peak_leistung_in_kW=max_peak_power_ac_grid, jahresverbrauch_in_kWh=total_energy_bought_year_kWh,
                                          spannungsebene=h2pp.strompreise.Spannungsebene[sim_config_dict["spannungsebene"]],
                                          ort=sim_config_dict["ort"]) * max_peak_power_ac_grid

    if "nur_beschaffungskosten" in sim_config_dict:
        if sim_config_dict["nur_beschaffungskosten"]:
            warnings.warn("Leistungspreis wird ignoriert!")
            lpr = 0.0

    print("Leistungspreis: ", lpr, "€") if verbose else None
    total_cost_electricity_buy += lpr

    opex_params = OpexParameters(total_cost_electricity_buy=total_cost_electricity_buy,
                                 total_cost_h2_buy=total_cost_h2_buy,
                                 total_revenue_heat_sell=total_revenue_heat_sell,
                                 total_revenue_electricity_sell=total_revenue_electricity_sell)

    # In der TCO Berechnung (siehe calculate_tco) ist es prinzipiell möglich, über das OPEX params dict
    # für jedes Jahr manuell Energiekosten anzugeben
    # TODO diese werden derzeit aber noch recht "hacky" an das TCO Modul übergeben (siehe "Hack" in der TCO.py Calculation - "custom_per_year_jc"),
    #  da die TCO berechnung momentan für OPEX keine variablen quantities zulässt.
    #  Hier wäre eine etwas ausführlichere Anpassung in der tco.py nötig um es "schön" zu machen, zunächst daher so gelassen.

    for year in range(2025, 2056):
        # Für jedes Jahr werden zunächst dieselben Energiekosten und damit auch Bezüge aus dem Markt angenommen.
        dict_sim_opex_results[year] = opex_params

        # TODO ggfs später verschiedene Energiekosten in den Jahren. Hier müsste man schauen wie man es laufzeittechniscch
        #  macht, bspw. nur erstes und letztes Jahr betrachten, verschiedene Energiekostenszenarien dafür annehmen, jeweils
        #   optimieren und zwischen diesen Jahren interpolieren o. Ä.


    capex_params = CapexParameters(cost_data_identifier="STANDARD",
                                   p_el=p_el,
                                   p_fc=p_fc,
                                   m_tank=m_tank,
                                   c_battery_refcase_only=c_battery,
                                   m_tank_HP=sim_config_dict["HRS_Compressor"]["hp_tank_capacity_kg"],
                                   battery_lifetime_years=None if c_battery is None else lifetime_battery)

    tco_obj = calculate_tco(capex_params, dict_sim_opex_results)

    return EvaluationResult(
        tco=tco_obj,
        aufschlaege_strom_total_eur_per_kwh=steuern_umlagen_real,
        leistungspreis_summe=lpr,
        peak_power_year_kW=max_peak_power_ac_grid,
        total_consumption_year_kwh=total_energy_bought_year_kWh
    )


def prep_sim_config_dict(parsed_json: Dict, config_file_path: str):
    """
    Einige aufbereitungen für die Simulation.
    Das dict (parsed_json) wird inplace verändert.

    config_file_path ist der vollständige Pfad zur JSON Datei (e.g. C:/Users/.../config.json). Wird benötigt, um die
    Pfade in der JSON Datei relativ zu diesem Pfad zu interpretieren

    Aufbereitungen umfassen v. a.:
    - Erweiterung oder Mittelwertbildung für Zeitreihen die nur einen Tag oder ein ganzes Jahr repräsentieren
    - Normalisierung der Zeitreihen auf eine einheitliche Schrittweite (Schrittweite der Simulation)
    - Aggregation der Zeitreihen für alle Erzeuger und Verbraucher für jede Jahreszeit, nach Energietyp
    - synthetische Generierung von PV- und BDEW-Zeitreihen, sofern in der JSON Datei angegeben
    - Generierung der Zeitreihe für den Börsenstrompreis (Einlesen der spezifizierten File und Mittelung mittels
    helperFunctions.netztransparenz_importer, s.u.)
    - Abschätzung von Jahresbedarf und Peak für den Optimierer (Optimierer braucht einen Preis pro kWh, aber der ergibt
    sich eigentlich erst aus dem konkreten Ergebnis, da er über die Netzentgelte vom Verbrauchsverhalten abhängt.
    Daher zunächst abschätzen, um auf Basis halbwegs realistischer Werte optimieren zu können. In der TCO können dann
    zumindest die "realen" Kosten der so gefundenen Kontrollstrategie berechnet werden)
    """
    #
    #

    freq_in_min = parsed_json["base_sim_interval"]
    sim_sow = parsed_json["sim_start_of_week"]

    # Create generator/consumer time series (aggregate all time series for all generators/consumers for every season)

    dc_generators_all_ts = {}
    ac_generators_all_ts = {}
    hydrogen_generators_all_ts = {}

    dc_consumers_all_ts = {}
    ac_consumers_all_ts = {}
    hydrogen_consumers_350_all_ts = {}
    hydrogen_consumers_700_all_ts = {}

    for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
        # Initialize the time series for the producers and consumers of electricity and hydrogen...
        dc_generators_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)
        ac_generators_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)
        hydrogen_generators_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)

        dc_consumers_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)
        ac_consumers_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)
        hydrogen_consumers_350_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)
        hydrogen_consumers_700_all_ts[jahreszeit.name] = np.zeros((24 * 60 * 7) // freq_in_min + 1)

    # Aggregation of time series for all generators
    for generator in parsed_json["generators"]:

        for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
            if generator['calculation_type'] == "constant_power":
                power_value = generator['parameters']['power_value']
                generator_ts = power_value * np.ones((24 * 60 * 7) // freq_in_min + 1)

            elif generator['calculation_type'] == "time_series":

                # Normalization of paths in order to cope with Windows and Unix paths
                config_dir = os.path.dirname(config_file_path)
                normalized_path_conf = os.path.normpath(config_dir)
                file_path_x = os.path.join(normalized_path_conf,
                                           os.path.normpath(generator['parameters']['file_path']))

                # Based on the scope of the time series, different import functions need to be used
                if generator['parameters']['contains'] == 'one_day':
                    generator_ts = h2pp.generators.import_and_normalize_one_day_time_series_csv(csv_path=file_path_x,
                                                                                                base_sim_interval_in_min=freq_in_min)

                elif generator['parameters']['contains'] == 'one_week':
                    generator_ts = h2pp.generators.import_and_normalize_one_week_time_series_csv(
                        csv_path=file_path_x,
                        base_sim_interval_in_min=freq_in_min,
                        start_of_week=parsed_json["sim_start_of_week"],
                        jahreszeit=jahreszeit)

                elif generator['parameters']['contains'] == 'whole_year':
                    generator_ts = h2pp.generators.typical_week_from_yearly_data_csv(csv_path=file_path_x,
                                                                                     jahreszeit=jahreszeit,
                                                                                     start_of_week=sim_sow,
                                                                                     base_sim_interval_in_min=freq_in_min)

                else:
                    raise ValueError(
                        f"Unknown / invalid 'contains' value {generator['parameters']['contains']} for generator {generator['name']}")

            # PV time series calculation
            elif (generator['energy_type'] == 'electricity_dc') and (generator['calculation_type'] == "pv_calculation"):
                lat = generator['parameters']['latitude']
                lon = generator['parameters']['longitude']
                peakpower = generator['parameters']['peakpower']
                surface_tilt = generator['parameters']['surface_tilt']
                surface_azimuth = generator['parameters']['surface_azimuth']
                pvtechchoice = generator['parameters']['pvtechchoice']

                generator_ts = h2pp.generators.create_pv_plant_time_series(latitude=lat, longitude=lon,
                                                                           jahreszeit=jahreszeit,
                                                                           peakpower_in_kW=peakpower,
                                                                           # 1.4 MWp, in Anlehnung an zu installierende Leistung EUREF Campus Düsseldorf
                                                                           base_sim_interval_in_min=freq_in_min,
                                                                           sim_sow=sim_sow,
                                                                           surface_tilt=surface_tilt,
                                                                           surface_azimuth=surface_azimuth,
                                                                           pvtechchoice=pvtechchoice
                                                                           )
            else:
                raise ValueError(
                    f"Unknown / invalid calculation type {generator['calculation_type']} for generator {generator['name']} or wrong energy_type!")

            # store the calculated time series for this generator in this season in the generator dict
            # e.g. jahreszeit.name turns Jahreszeit.SOMMER into "SOMMER" (with the values/names specified specified in class Jahreszeit)
            if generator['energy_type'] == 'electricity_dc':
                dc_generators_all_ts[jahreszeit.name] += generator_ts
            elif generator['energy_type'] == 'electricity_ac':
                ac_generators_all_ts[jahreszeit.name] += generator_ts
            elif generator['energy_type'] == 'hydrogen':
                if generator['pressure'] == 30:
                    hydrogen_generators_all_ts[jahreszeit.name] += generator_ts
                else:
                    raise NotImplementedError("Currently only 30 bar hydrogen generators are supported!")

    # propagate the calculated time series for all generators to the parsed_json dict
    parsed_json['dc_generators_all_ts'] = dc_generators_all_ts
    parsed_json['ac_generators_all_ts'] = ac_generators_all_ts
    parsed_json['hydrogen_generators_all_ts'] = hydrogen_generators_all_ts

    # Create consumer time series
    for consumer in parsed_json["consumers"]:

        for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
            if consumer['calculation_type'] == "constant_power":
                power_value = consumer['parameters']['power_value']
                consumer_ts = power_value * np.ones((24 * 60 * 7) // freq_in_min + 1)

            elif consumer['calculation_type'] == "time_series":

                # Normalization of paths in order to cope with Windows and Unix paths
                config_dir = os.path.dirname(config_file_path)
                normalized_path_conf = os.path.normpath(config_dir)
                file_path_x = os.path.join(normalized_path_conf,
                                           os.path.normpath(consumer['parameters']['file_path']))

                # Based on the scope of the time series, different import functions need to be used
                if consumer['parameters']['contains'] == 'one_day':
                    consumer_ts = h2pp.generators.import_and_normalize_one_day_time_series_csv(csv_path=file_path_x,
                                                                                               base_sim_interval_in_min=freq_in_min)

                elif consumer['parameters']['contains'] == 'one_week':
                    consumer_ts = h2pp.generators.import_and_normalize_one_week_time_series_csv(
                        csv_path=file_path_x,
                        base_sim_interval_in_min=freq_in_min,
                        start_of_week=parsed_json["sim_start_of_week"],
                        jahreszeit=jahreszeit)

                elif consumer['parameters']['contains'] == 'whole_year':
                    consumer_ts = h2pp.generators.typical_week_from_yearly_data_csv(csv_path=file_path_x,
                                                                                    jahreszeit=jahreszeit,
                                                                                    start_of_week=sim_sow,
                                                                                    base_sim_interval_in_min=freq_in_min)

                else:
                    raise ValueError(
                        f"Unknown / invalid 'contains' value {consumer['parameters']['contains']} for generator {consumer['name']}")

            elif (consumer['energy_type'] == 'electricity_ac') and (consumer['calculation_type'] == "BDEW"):
                # Zum Demand:
                # https://www.bdew.de/energie/standardlastprofile-strom/

                jahresverbrauch_in_kWh = consumer['parameters']['yearly_consumption']
                kundengruppe_str = consumer['parameters']['profile']

                # Check if Kundengruppe is valid
                if kundengruppe_str not in [member.value for member in h2pp.generators.BDEW_Kundengruppe]:
                    raise ValueError(f"{kundengruppe_str} is not a valid BDEW Kundengruppe!")
                kdg_objekt = h2pp.generators.BDEW_Kundengruppe[
                    kundengruppe_str]  # turns into sth. like h2pp.generators.BDEW_Kundengruppe.G6 at runtime

                consumer_ts = h2pp.generators.create_bdew_consumption_time_series(kundengruppe=kdg_objekt,
                                                                                  start_of_week=sim_sow,
                                                                                  jahreszeit=jahreszeit,
                                                                                  annual_consumption=jahresverbrauch_in_kWh,
                                                                                  base_sim_interval_in_min=freq_in_min)

            else:
                raise ValueError(
                    f"Unknown / invalid calculation type {consumer['calculation_type']} for generator {consumer['name']} or wrong energy_type!")

            # store the calculated time series for this consumer in this season in the consumer dict
            if consumer['energy_type'] == 'electricity_ac':
                ac_consumers_all_ts[jahreszeit.name] += consumer_ts
            elif consumer['energy_type'] == 'electricity_dc':
                dc_consumers_all_ts[jahreszeit.name] += consumer_ts
            elif consumer['energy_type'] == 'hydrogen':
                if consumer['pressure'] == 700:
                    hydrogen_consumers_700_all_ts[jahreszeit.name] += consumer_ts
                elif consumer['pressure'] == 350:
                    hydrogen_consumers_350_all_ts[jahreszeit.name] += consumer_ts
                else:
                    raise NotImplementedError("Currently only 700 and 350 bar hydrogen consumers are supported!")

    # propagate the calculated time series for all generators to the parsed_json dict
    parsed_json['dc_consumers_all_ts'] = dc_consumers_all_ts
    parsed_json['ac_consumers_all_ts'] = ac_consumers_all_ts
    parsed_json['hydrogen_consumers_350_all_ts'] = hydrogen_consumers_350_all_ts
    parsed_json['hydrogen_consumers_700_all_ts'] = hydrogen_consumers_700_all_ts

    # ======================== Hier Aufbereitung für Strompreise ========================

    # 1. Börsenstrompreis einlesen (Mittelwertbildung und Resampling erfolgt erst unten im Jahreszeit-Loop)
    # Prinzipiell erfolgt die Ergänzung der ganzen Steuern, Umlagen, Netzentgelte dann erst in der Simulation bzw.
    # TCO Berechnung.

    parsed_json['electricity_market_base_price_ts'] = {} # Wird unten mit Zeitreihen für Strompreis in den typischen Wochen befüllt

    config_dir = os.path.dirname(config_file_path)
    normalized_path_conf = os.path.normpath(config_dir)
    file_path_sp = os.path.join(normalized_path_conf,
                               os.path.normpath(parsed_json['strompreis_csv']))

    df_prices_strom_spotmarkt = helperFunctions.netztransparenz_importer(file_path=file_path_sp)

    # 2. Initialisierungen für Abschätzung für Jahresbedarf und Peak/Spitzenlast
    inv_eff = parsed_json["inverter_efficiency"]
    jahresbedarf_abschaetzung = 0
    peak_abschaetzung = 0

    for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
        # TODO: Hier könnte man erwägen, statt diesem "Netztransparenz"-Exporterformat ein aufbereitetes Standardformat
        #  festzulegen, in das die Daten zu bringen sind o.Ä. (bessere Handhabung von eigenen, hypothetischen Werten
        #  oder Ausland

        # Dynamisch die monate wählen, basierend darauf, ob wir Winter, Sommer oder Übergang haben
        # Monate sind hard-coded in der typical_months() Funktion in generators.py festgelegt.
        months = h2pp.generators.typical_months(jahreszeit)

        # Mittelwertbildung/Resampling für den Börsenpreis je nach Jahreszeit
        ts_resampled_values_strompreis = helperFunctions.typical_week(df_prices_strom_spotmarkt, months, sim_sow,
                                                                          freq_in_min)
        parsed_json['electricity_market_base_price_ts'][
            jahreszeit.name] = ts_resampled_values_strompreis


        # Abschätzungen für Jahresbedarf und Peak/Spitzenlast erweitern um diese Jahreszeit
        num_weeks = helperFunctions.sum_days_in_months(months) / 7
        consumption_ac_equiv_total_ts = ((dc_consumers_all_ts[jahreszeit.name] / inv_eff) + ac_consumers_all_ts[jahreszeit.name])
        generation_ac_equiv_total_ts = ((dc_generators_all_ts[jahreszeit.name] * inv_eff) + ac_generators_all_ts[jahreszeit.name])
        net_consumption_abschaetzung_ts = consumption_ac_equiv_total_ts - generation_ac_equiv_total_ts
        net_consumption_abschaetzung_ts[net_consumption_abschaetzung_ts < 0] = 0 # Consumption may not be negative (If we have excess generation, we have simply no grid feed-in, not "a negative" one)
        jahresbedarf_abschaetzung += np.sum(net_consumption_abschaetzung_ts) * (
                    freq_in_min / 60) * num_weeks  # kWh. Prinzipiell die 1 Woche auf 1 Jahr hochrechnen (letzter, doppelter Intervallschritt der woche grob ignoriert, sollte insignifikant sein.)

        # Peak abgeschätzt OHNE Elektrolyseurleistung. Daher hier auch keine entgültige Bestimmung der Aufschläge, dies erfolgt erst in der run_simulation.
        peak_abschaetzung_jahreszeit = np.max(net_consumption_abschaetzung_ts)
        peak_abschaetzung = max(peak_abschaetzung, peak_abschaetzung_jahreszeit)

    parsed_json['jahresbedarf_abschaetzung_fuer_strompreis'] = jahresbedarf_abschaetzung
    parsed_json['peak_abschaetzung_fuer_strompreis'] = peak_abschaetzung


    # =================================================================================================================


def optimize_h2pp(config_file_full_path: str, mode: Literal["normal", "battery_ref", "power_grid_only_ref"] = "normal",
                  pop_size=50, n_gen=100, **kwargs) -> (tco.TCO, Dict[str, go.Figure]):

    """
    Main function for the optimization of the H2PP system. The function will read the configuration file, does some
     preparations (reading and generating time series for consumers and generators, resampling and averaging them
        for the different seasons, etc.), set up the optimization problem, run the optimization and return the results.
    @param config_file_full_path:  Full path to the configuration file (JSON) containing the simulation parameters etc.
    @param mode: Mode of the optimization. Can be either "normal" (default), "battery_ref" or "power_grid_only_ref".
                  Here, "normal" is an optimization for an H2PP system, while "battery_ref" is the battery reference case
                  (no electrolyzer, tank, fuel cell etc. but instead a battery), and "power_grid_only_ref" is a reference
                  case where no additional infrastructure is considered (energy only from grid and local production, no
                  local storage etc.)
    @param pop_size: population size for the genetic algorithm. only necessary if mode == "normal".
    @param n_gen: number of generations for the genetic algorithm. only necessary if mode == "normal".
    @param kwargs: kwargs to be passed to the eval_scenario function (e.g. verbose=True to get more detailed output on
    the optimization process, like estimated Jahresbedarf/Peak etc.)
    @return: A 2-tuple containing the TCO object of the found optimum and a dictionary of plotly figures (one for each
    Jahreszeit) with the simulation results (optimal control strategie for components/consumptions etc.)
    """

    if mode not in ["normal", "battery_ref", "power_grid_only_ref"]:
        raise ValueError(f"Invalid mode {mode} for optimization. Must be either 'normal', 'battery_ref' or "
                         f"'power_grid_only_ref'.")

    with open(config_file_full_path) as user_file:
        parsed_json = json.load(user_file)

    # Note that the function will mutate the dict inplace, as dictionaries are passed by reference in Python by default
    prep_sim_config_dict(parsed_json=parsed_json, config_file_path=config_file_full_path)

    p_el = None
    p_fc = None
    m_tank = None
    compress_before_storing = False
    c_battery = None

    tco_obj = None

    if mode == "normal":

        problem = H2PP_Standard_MixedVariableProblem(sim_config_dict=parsed_json)

        algorithm = MixedVariableGA(
            pop_size=pop_size)

        res = minimize(problem,
                       algorithm,
                       ('n_gen', n_gen),
                       # termination=('n_evals', 50),
                       seed=1,
                       verbose=True)  # verbose=True, um die Ergebnisse zu sehen (für mich zum "debugging")

        print("Best solution found: \nX = %s\nF = %s" % (res.X, res.F))

        # =================================================================================================================

        # Optimales Ergebnis plotten:
        # Hierfür müssen zunächst die Parameter des optimalen Ergebnisses bezogen und erneut eine Simulation damit je Jahreszeit durchgeführt werden
        paramset = problem._retrieve_parameter_set(res.X)

        p_el = paramset["p_el"]
        p_fc = paramset["p_fc"]
        m_tank = paramset["m_tank"]
        compress_before_storing = paramset["compress_before_storing"]
        c_battery = None

        eval_res = eval_scenario(p_el, p_fc, m_tank, compress_before_storing, c_battery=c_battery,
                                sim_config_dict=parsed_json, **kwargs)

    elif mode == "battery_ref":
        c_battery, best_eval_res = get_optimum_for_battery_refcase_only(parsed_json, **kwargs)
        print(f"Best battery capacity for the reference case: {c_battery} kWh")
        print(f"NPV for the reference case with the best battery capacity: {best_eval_res.tco.npv_total} EUR")
        eval_res = best_eval_res

    elif mode == "power_grid_only_ref":
        eval_res = eval_scenario(p_el=None, p_fc=None, m_tank=None, compress_before_storing=False, c_battery=None,
                                sim_config_dict=parsed_json, **kwargs)
        print(eval_res.tco.npv_total)

    figs = {}

    tco_obj = eval_res.tco

    tco_fig = tco_obj.plot_stacked_bar_over_period()
    figs["TCO"] = tco_fig # TODO I think we do never use this here anymore as we now directly get the TCO figure from the returned tco_obj, but please double-check this.

    for jahreszeit in [Jahreszeit.SOMMER, Jahreszeit.UEBERGANG, Jahreszeit.WINTER]:
        sim_results = run_simulation(sim_config_dict=parsed_json, jahreszeit=jahreszeit, p_el=p_el, p_fc=p_fc,
                                     m_tank=m_tank, compress_before_storing=compress_before_storing,
                                     c_battery=c_battery)['sim_results']

        title = f"Simulationsergebnisse ({jahreszeit.name}) für P<sub>EL</sub>={np.round(p_el, 1) if p_el is not None else 0} kW, P<sub>FC</sub>={np.round(p_fc, 1) if p_fc is not None else 0} kW, m<sub>Tank</sub>={np.round(m_tank) if m_tank is not None else 0} kg, B<sub>compr</sub>={compress_before_storing}, C<sub>batt</sub>={np.round(c_battery) if c_battery is not None else 0} kWh"
        figs[jahreszeit.name] = helperFunctions.process_results_and_return_plot(sim_results,
                                                                                titlestring=title,
                                                                                simulation_interval=parsed_json[
                                                                                    "base_sim_interval"],
                                                                                start_of_week=parsed_json[
                                                                                    "sim_start_of_week"],
                                                                                electricity_prices=
                                                                                parsed_json['electricity_market_base_price_ts'][
                                                                                    jahreszeit.name],
                                                                                evalResult=eval_res)
    return tco_obj, figs
