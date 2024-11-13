'''

Free-floating script to calculate the necessary fuel cell power and tank mass to overcome a blackout of a given duration.

There are some additional restrictions and requirements for the used JSON in comparison to the "normal" JSONs used in the rest of the project:

- Hydrogen generators and consumers are ignored.
- The Electrolyser MUST specify a fixed nominal power (in kW) (no range allowed).
- any given ranges for fuel cells will be discarded, only the electrical efficiency is considered, as
    a) we do not care for the heat revenue in this study
    b) the output power of the fuel cell will be chosen to be "sufficiently high" to cover the demand on this blackout/"island mode"

'''

import json
import math
import os
import warnings

import pandas as pd
from oemof import solph
import numpy as np
from oemof.tools.debugging import SuspiciousUsageWarning
from oemof.solph import views

from h2pp import helperFunctions
from h2pp.generators import Jahreszeit, create_electrolyzer, create_fuel_cell_chp, create_simple_inverter, \
    create_h2_storage, convert_kWh_to_kg_H2
from h2pp.optimizer import prep_sim_config_dict
from h2pp.helperFunctions import get_max_depth
from matplotlib import pyplot as plt

# switch on SuspiciousUsageWarning
warnings.filterwarnings("always", category=SuspiciousUsageWarning)

def _calculate_fc_power_and_tank_mass(parsed_json, file_path,
                                      freq_in_min,
                                      plot_fc_and_tank=False):

    """
    Berechnet eine obere Schranke für die Brennstoffzellenleistung und den Tank.
    Simuliert das Energiesystem mit diesem Parametern für die jeweiligen Komponente für eine gesamte Woche + 2 Tage.
    Bestimmt zu jedem Zeitpunkt die Leistung der Brennstoffzelle und den Füllstand des Tanks (wobei der Tank zum Simulationsstart als Füllstand die berechnete obere Schranke hat und sukzessive entleert wird).
    :param parsed_json:
    :param freq_in_min:
    :return:
    """


    # Note that the function will mutate the dict inplace, as dictionaries are passed by reference in Python by default
    prep_sim_config_dict(parsed_json=parsed_json, config_file_path=file_path)

    # From here on the script has huge similarities to the run_simulation function in the simulator.py file
    # however we still "reimplement" the important parts here to keep the run_simulation function still readable...

    # Baue das Energysystem auf und simuliere es mit einer "ausreichend großen Größe" für Brennstoffzelle und Tank.
    # "ausreichend groß" = orientiert an einer absolut oberen Schranke, die sich u.a. aus den maximalen Verbrauchsspitzen ergibt.

    # Do everything for a "worst case" winter scenario
    # TODO: even better would be an repetitive "coldest winter day" scenario.
    jahreszeit = Jahreszeit.WINTER

    if (24*60) % freq_in_min != 0:
        raise ValueError(f"Base simulation interval {freq_in_min} is not a divisor of 24*60 minutes!")

    my_index = pd.date_range(start='2020-01-01',
                                 end='2020-01-10',
                                 inclusive='both',  # rechtsoffenes intervall
                                 freq=f"{freq_in_min}min")

    my_energysystem = solph.EnergySystem(timeindex=my_index, infer_last_interval=True)

    # here, we do NOT need thermal or H2 FCEV buses as in our "backup supply" scenario we are not interested in the heat revenue nor in any car-related stuff (assume the cars fill their tanks at an external HRS or are not used.)
    bel_ac = solph.buses.Bus(label='electricity_ac')
    bel_dc = solph.buses.Bus(label='electricity_dc')
    bel_th = solph.buses.Bus(label='thermal') # technically we dont really need this for this case, but we need to specify some thermal bus for the fuel cell..
    bhydr_30 = solph.buses.Bus(label="h2_30bar")

    my_energysystem.add(bel_ac, bel_dc, bhydr_30, bel_th)

    # Excess electricity sink to get rid of e.g. overproduction in PV when the electrolyzer is not able to handle the load ("PV higher than consumption")
    # We need to tell the optimizer that this is not the way to go by giving a penalty (positive costs) for this case
    # => so that the system will first try to satisfy any demand and THEN discard (e. g., turn of the PV plant) the rest
    # otherwise, the optimizer would think feeding energy to the excess is not more or less favorable than saving it
    # in the tank or directly using it to satisfy demand
    vc = [1] * ((24 * 60 * 9) // freq_in_min + 1)
    my_energysystem.add(solph.components.Sink(label="excess_bel_ac", inputs={bel_ac: solph.Flow(variable_costs=vc)}))
    my_energysystem.add(solph.components.Sink(label="excess_bth", inputs={bel_th: solph.Flow()}))

    # Initialize the time series for the producers of electricity and hydrogen...
    # (Attention, here we assume that we have no explicit other hydrogen producers, e.g. a steam reformer or so -
    # we assume these will also be affected by the power loss(?) TODO later check, as we never had such systems in our examples/use cases)
    generator_dc_electricity_ts = parsed_json['dc_generators_all_ts'][jahreszeit.name]
    generator_ac_electricity_ts = parsed_json['ac_generators_all_ts'][jahreszeit.name]

    # ==================

    consumed_ac_electricity_ts = parsed_json['ac_consumers_all_ts'][jahreszeit.name]
    consumed_dc_electricity_ts = parsed_json['dc_consumers_all_ts'][jahreszeit.name]


    # Verlängern die Zeitreihen auf 9 tage, indem wir die ersten 2 tage nochmal ranhängen (achtung, letzter Eintrag muss vorher rausgeschmissen werden "closed interval" (sonst doppelt)
    num_steps = ((24 * 60 * 2) // freq_in_min) + 1 # +1 wegen closed interval des simulation time index wieder. unten dann tatsächlich nur bis num_steps, weil der index bei 0 beginnt
    consumed_ac_electricity_ts = np.concatenate((consumed_ac_electricity_ts[:-1], consumed_ac_electricity_ts[:num_steps]))
    consumed_dc_electricity_ts = np.concatenate((consumed_dc_electricity_ts[:-1], consumed_dc_electricity_ts[:num_steps]))
    generator_ac_electricity_ts = np.concatenate((generator_ac_electricity_ts[:-1], generator_ac_electricity_ts[:num_steps]))
    generator_dc_electricity_ts = np.concatenate((generator_dc_electricity_ts[:-1], generator_dc_electricity_ts[:num_steps]))

    electricity_dc_generators = solph.components.Source(label='Electricity_DC_Generation_Ges', outputs={bel_dc: solph.Flow(
        fix=generator_dc_electricity_ts, nominal_value=1
        # nominal_value auf 1, da timeseries bereits skaliert
    )})

    electricity_ac_generators = solph.components.Source(label='Electricity_AC_Generation_Ges',
                                                        outputs={bel_ac: solph.Flow(
                                                            fix=generator_ac_electricity_ts, nominal_value=1
                                                        )})

    my_energysystem.add(electricity_ac_generators, electricity_dc_generators)


    electricity_consumers_ac = solph.components.Sink(label='Electricity_Consumption_AC_Ges', inputs={bel_ac: solph.Flow(
            fix=consumed_ac_electricity_ts, nominal_value=1
        )})

    electricity_consumers_dc = solph.components.Sink(label='Electricity_Consumption_DC_Ges',
                                                       inputs={bel_dc: solph.Flow(
                                                           fix=consumed_dc_electricity_ts, nominal_value=1
                                                       )})

    my_energysystem.add(electricity_consumers_dc, electricity_consumers_ac)

    wirkungsgrad_elektrolyseur = parsed_json["electrolyzer"]["efficiency"]
    leistung_elektrolyseur = parsed_json["electrolyzer"]["fixed_p"]  # kW
    my_energysystem.add(create_electrolyzer(input_bus_el=bel_dc,
                                            output_bus_h2=bhydr_30,
                                            electrical_efficiency=wirkungsgrad_elektrolyseur,
                                            nominal_power=leistung_elektrolyseur))

    # Inverter fur AC/DC
    inv_eff = parsed_json["inverter_efficiency"]
    my_energysystem.add(create_simple_inverter(input_bus=bel_ac, output_bus=bel_dc, efficiency=inv_eff, label='Inverter_AC_DC'))
    my_energysystem.add(create_simple_inverter(input_bus=bel_dc, output_bus=bel_ac, efficiency=inv_eff, label='Inverter_DC_AC'))


    # calculate "upper bound" for the necessary fuel cell power output
    # as we directly specify the output power, the only thing that needs to be scaled is the AC power (AC/DC conversion necessary)
    # (fuel cell outputs DC energy)
    consumption_dc_equiv_total_ts = ((consumed_ac_electricity_ts / inv_eff) + consumed_dc_electricity_ts)
    fc_upper_bound_power = np.max(consumption_dc_equiv_total_ts)

    eta_fc_el = parsed_json["fuelcell"]["efficiency_electric"]

    # add a bus acting as a penalty bottleneck to tell the optimizer that local consumption of e.g. PV is better than utilizing tank/fuel cell
    # furthermore (and this is even more important) to prevent the electrolyzer from directly utilizing the electricity from the fuel cell to produce H2 again with the electrolyzer (would be an energy-costly "loop").
    bel_penalty_dc = solph.buses.Bus(label='bel_penalty_dc')
    my_energysystem.add(bel_penalty_dc)

    my_energysystem.add(create_fuel_cell_chp(input_bus_h2=bhydr_30,
                                             output_bus_el=bel_penalty_dc,
                                             output_bus_th=bel_th, # we only set this here as we cannot set it to "none" and it has zero output anyway as we set the thermal efficiency to 0 below.
                                             electrical_efficiency=eta_fc_el,
                                             thermal_efficiency=0,
                                             nominal_power_el=fc_upper_bound_power + 10)) # 10 kW reserve for security reasons

    # the penalty bus however gives 1:1 its inputs to the bel_dc bus but with some arbitrary costs > 0
    my_energysystem.add(solph.components.Converter(label='penalty_transformer',
                                                      inputs={bel_penalty_dc: solph.Flow(variable_costs=vc)},
                                                      outputs={bel_dc: solph.Flow()}))

    # Adding the tank.
    # Max tank capacity depends on the consumers again; we can only ensure feasibility if we make the tank big enough to cover the full demand over the week (+2 days) alone
    el_upper_bound_sum_kwh = np.sum(consumption_dc_equiv_total_ts) / (freq_in_min / 60)  # in kWh
    kwhs_needed_tank = el_upper_bound_sum_kwh / eta_fc_el
    m_tank_min = convert_kWh_to_kg_H2(kwhs_needed_tank)

    my_energysystem.add(create_h2_storage(bus_h2=bhydr_30, storage_capacity_in_kg=m_tank_min + 10, # incl. 10 kg reserve
                                          initial_storage_level=1.0)) # tank needs to start full


    # only for testing purposes, plot the created energy system graph
    # gr = ESGraphRenderer(energy_system=my_energysystem, filepath="energy_system_techmachbarkeit", img_format="pdf")
    # gr.view()


    # ===========================

    # Simulation mit Tank auf obere Schranke (Start auch mit diesem Wert) und Brennstoffzelle auf oberer Schranke (alternativ wäre auch eine Implementierung OHNE explizite Begrenzung möglich, dann müsste ich meine BZ-Generierungsmethode aber erweitern / neu schreiben).

    # initialise operational model (create problem)
    om = solph.Model(my_energysystem)

    # set tee to True to get solver output
    om.solve(solver='cbc', solve_kwargs={'tee': False})

    # get results
    my_energysystem.results["main"] = solph.processing.results(om)
    my_energysystem.results["meta"] = solph.processing.meta_results(om)

    # define an alias for shorter calls below
    results = my_energysystem.results["main"]

    # 5. Abgriff der Ergebnisse:
    #   Zu jedem Zeitpunkt:
    #   - Tankfüllung (kg)
    #   - Leistung Brennstoffzelle (kW)
    #   => hieraus können dann die Mindestbedarfe abgeleitet werden

    results = views.convert_keys_to_strings(results)
    bz_el = results[('Brennstoffzelle', 'bel_penalty_dc')]['sequences'].values[:-2, 0]

    # Storage vom H2 Tank
    # siehe hier bei GenericStorage: https://oemof-solph.readthedocs.io/en/latest/usage.html
    column_name = (('H2Tank', 'None'), 'storage_content')
    SC = views.node(results, 'H2Tank')['sequences'][column_name]
    tank_fuellstand_kg = SC.values[:-2] / 33.3  # 33.3 kWh pro kg H2 # TODO dynamische eingabe -> evtl. die CONV_RATE_kWh_to_kg_H2 in der generators.py bzw. die Konvertierungsfunktionen da nutzen

    if plot_fc_and_tank:
        # Lets plot the bz_el and tank_fuellstand_kg in a diagram (separate y-axis for each.)
        fig, ax1 = plt.subplots()

        color = 'tab:red'
        ax1.set_xlabel('time')
        ax1.set_ylabel('Brennstoffzelle (kW)', color=color)
        ax1.plot(bz_el, color=color)
        ax1.tick_params(axis='y', labelcolor=color)

        ax2 = ax1.twinx()
        color = 'tab:blue'
        ax2.set_ylabel('Tankfüllung (kg)', color=color)
        ax2.plot(tank_fuellstand_kg, color=color)
        ax2.tick_params(axis='y', labelcolor=color)

        plt.show()

        print("DONE")

    # return Fuel Cell Power draw and the tank mass (starting from the calculated upper bound) at each timestep for the 9 days
    return bz_el, tank_fuellstand_kg


def _get_minimum_needed_parameter(bz_el, tank_fuellstand_kg, blackout_interval_duration_n_steps: int, freq_in_min: int):
    # todo here we might check if freq_in_min is a divisor of 24*60*7 and blackout_interval_duration_n_steps is also a valid value

    # collect the needed fuel cell power value and min tank mass for each possible starting timestep of the blackout:
    fc_powers = []
    tank_masses = []

    # Bestimmen für jeden Startzeitpunkt t0 (nur über die ersten 7 Tage nötig, danach redundant):
    # über den Zeitraum t0, t1 (je nach Input bis zu t1=t0+2Tage):
    #       a) Brennstoffzellenleistung:
    #           - via max(P_FC[t0,t1])
    # - minimal vorrätig zu haltende Tankfüllung:
    #       => Überlegung: die größtmögliche Differenz die sich zwischen einem lokalen Max (kann auch Start sein) und
    #       einem zeitlich DANACH folgendem lokalen Min ergibt, ist die minimal nötige Tankkapazität (siehe get_max_depth Funktion)

    for interval_start in range(0, (24 * 60 * 7) // freq_in_min):
        end = interval_start + blackout_interval_duration_n_steps  # closed interval, must have enough tank content etc. at the end of the interval/beginning of next
        fc_power_max = np.max(bz_el[interval_start:end + 1])
        tank_ts = tank_fuellstand_kg[interval_start:end + 1]

        max_tank_discharge_depth = get_max_depth(tank_ts)

        fc_powers.append(fc_power_max)
        tank_masses.append(max_tank_discharge_depth)

    return fc_powers, tank_masses

def blackout_check_multi_plot(file_path: str, scenario_name: str):

    """
    Runs the blackout check using the given JSON config file and plots the needed fuel cell power (kW) and tank mass (kg)
    on the y-axis, for each possible blackout duration (0 to 48 hours, step size based on the base simulation interval)
    (x-axis), in a single plot.

    @param file_path: The file path of the JSON config file to use for the simulation
    @param scenario_name:
    @return: 2-tuple of:
        - a generated plotly figure showing the results (fuel cell power and tank mass needed to overcome a blackout of different durations) and
        - (a simplified) matplotlib plot, containing only the needed tank mass over the time (redundant, only for potential better visualization)
    """

    with open(file_path) as user_file:
        parsed_json = json.load(user_file)

    freq_in_min = parsed_json["base_sim_interval"]

    # freq_in_min, 2*freq_in_min, ... 24*60*2
    list_of_all_durations = [freq_in_min * i for i in range(1, (24*60*2 // freq_in_min) + 1)]

    list_of_needed_fc_power = []
    list_of_needed_tank_mass = []

    bz_el, tank_fuellstand_kg = _calculate_fc_power_and_tank_mass(parsed_json, file_path, freq_in_min)

    for duration in list_of_all_durations:
        blackout_interval_duration_n_steps = duration // freq_in_min
        fc_powers, tank_masses = _get_minimum_needed_parameter(bz_el, tank_fuellstand_kg,
                                                               blackout_interval_duration_n_steps, freq_in_min)

        required_fc_power = np.max(fc_powers)
        required_tank_mass = np.max(tank_masses)
        list_of_needed_fc_power.append(required_fc_power)
        list_of_needed_tank_mass.append(required_tank_mass)
        print(duration)

    list_of_all_durations_in_h = [d / 60 for d in list_of_all_durations]


    # plot the fc_powers and tank_masses against the blackout duration. One plot for each; in the same figure.
    import plotly.express as px
    import plotly.graph_objects as go

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list_of_all_durations_in_h,
        y=list_of_needed_fc_power,
        mode='lines+markers',
        name='Brennstoffzellenleistung [kW]'))

    fig.add_trace(go.Scatter(
        x=list_of_all_durations_in_h,
        y=list_of_needed_tank_mass,
        mode='lines+markers',
        name='Tankmasse [kg]'))

    fig.update_layout(
        title='Fuel Cell Power and Tank Mass needed to overcome a blackout of '
              'different durations', #if include_title else None,
        xaxis_title='Dauer der Stromunterbrechung [h]',
        yaxis_title='Leistung [kW] / Masse [kg]',
        template='plotly_white',
        xaxis=dict(
            tickmode='linear',
            dtick=4),

        font=dict(
            size=12
        )


    )


    # also for the tank as simple matplotlib plot
    plt.plot(list_of_all_durations_in_h, list_of_needed_tank_mass)
    plt.xlabel("Dauer der Stromunterbrechung [h]")
    plt.ylabel("Nötige Masse an H2 [kg]")
    return fig, plt

def blackout_check(blackout_duration_min: int, file_path: str):
    """
    For one given blackout duration, calculate the needed fuel cell power and tank mass to overcome the blackout.
    @param blackout_duration_min: The duration of the blackout in minutes. Must be a multiple of the base simulation interval.
    @param file_path: The file path of the JSON config file to use for the simulation
    @return: A 2-tuple of:
        - a list of the Fuel Cell Power required to overcome the blackout at each possible starting point inside the week (one item in the list per starting point)
        - a list of the Tank Capacity required to overcome the blackout at each possible starting point inside the week (one item in the list per starting point)
    """

    with open(file_path) as user_file:
        parsed_json = json.load(user_file)

    freq_in_min = parsed_json["base_sim_interval"]

    # Error Handling: Duration must be at least as long as the simulation interval, but no longer than two days.
    if blackout_duration_min < freq_in_min:
        raise ValueError("The blackout duration must be at least as long as the simulation interval.")

    if blackout_duration_min > 24*60*2:
        raise ValueError("The blackout duration must not be longer than two days.")


    blackout_interval_duration_n_steps = blackout_duration_min // freq_in_min # e.g. duration 60min and 15min intervals -> 4 steps


    # 2. Simulate the energy system and calculate the fuel cell power and the tank mass needed
    bz_el, tank_fuellstand_kg = _calculate_fc_power_and_tank_mass(parsed_json, file_path, freq_in_min)


    fc_powers, tank_masses = _get_minimum_needed_parameter(bz_el, tank_fuellstand_kg, blackout_interval_duration_n_steps, freq_in_min)

    # These contain, for each possible begin of the blackout (one item in the list per starting point), the Fuel Cell Power and Tank Capacity required to overcome a blackout with the given duration.
    return fc_powers, tank_masses

def plot_fc_power_and_tank_mass(blackout_duration_min, file_path,
                                include_title=True):

    """
    For a given blackout duration, plot the needed fuel cell power and tank mass to overcome the blackout.
    The x-axis represents the starting time of the blackout, the y-axis the fuel cell power and tank mass needed to overcome the blackout.
    Therefore, the plot shows for EACH possible starting time of the blackout inside the week, the needed parameters to overcome it.
    Also, the maximum fuel cell power and tank mass over all possible starting times are plotted as horizontal lines,
    thus showing the needed parameters to overcome any blackout of the given duration irrespective of the starting time.

    @param blackout_duration_min: The duration of the blackout in minutes. Must be a multiple of the base simulation interval.
    @param file_path: The file path of the JSON config file to use for the simulation
    @param include_title: True/False: Whether to include a title in the plot or not.
    @return: Plotly figure containing the plot.
    """

    # Plot the fuel cell power and the tank mass against the time

    fc_powers, tank_masses = blackout_check(blackout_duration_min, file_path)

    # read JSON for freq_in_min and start_of_week
    with open(file_path) as user_file:
        parsed_json = json.load(user_file)

    freq_in_min = parsed_json["base_sim_interval"]
    start_of_week = parsed_json["sim_start_of_week"]

    # plot the fc_powers and tank_masses against the time, where the time on the x axis is converted to a weekday/time string (sth. like "Sa 15:30") using the number_to_day_hour function. using plotly
    import plotly.express as px
    import plotly.graph_objects as go

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=[helperFunctions.number_to_day_hour(interval_start, freq_in_min, start_of_week) for interval_start in
           range(len(fc_powers))],
        y=fc_powers,
        mode='lines+markers',
        name='Brennstoffzellenleistung [kW]'))

    fig.add_trace(go.Scatter(
        x=[helperFunctions.number_to_day_hour(interval_start, freq_in_min, start_of_week) for interval_start in
           range(len(tank_masses))],
        y=tank_masses,
        mode='lines+markers',
        name='Tankmasse [kg]'))

    # blackout duration text: give it as "xx minutes" if the duration is <= 60min, otherwise as "xx.yy hours" (with two decimal places)
    blackout_duration_text = f"{blackout_duration_min} minutes" if blackout_duration_min <= 60 else f"{blackout_duration_min / 60:.2f} hours"

    fig.update_layout(
        title=f'Fuel Cell Power and Tank Mass over the simulated period to '
              f'overcome a blackout with duration of {blackout_duration_text}, '
              f'starting at the given time' if include_title else None,
        xaxis_title='Zeit',
        yaxis_title='Leistung [kW] / Masse [kg]',
        template='plotly_white',
        xaxis=dict(
            tickangle=-45,
            nticks=32),
        font=dict(
            size=12
        )
    )

    # plot horizontal lines with the maxima of the fuel cell power and the tank mass and plot their values as text

    fig.add_trace(go.Scatter(
        x=[helperFunctions.number_to_day_hour(x, freq_in_min, start_of_week) for x in
           [0, math.floor(0.7 * len(fc_powers)), len(fc_powers) - 1]],
        y=[max(fc_powers), max(fc_powers), max(fc_powers)],
        mode="lines+text",
        name="Max. Brennstoffzellenleistung",
        text=["", f"Max Brennstoffzellenleistung: {max(fc_powers):.2f} kW", ""],
        textposition="top center"
    ))

    # analog for the tank mass
    fig.add_trace(go.Scatter(
        x=[helperFunctions.number_to_day_hour(x, freq_in_min, start_of_week) for x in
           [0, math.floor(0.7 * len(tank_masses)), len(tank_masses) - 1]],
        y=[max(tank_masses), max(tank_masses), max(tank_masses)],
        mode="lines+text",
        name="Max. Tankmasse",
        text=["", f"Max. Tankmasse: {max(tank_masses):.2f} kg", ""],
        textposition="top center"
    ))

    return fig
