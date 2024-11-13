import warnings

import numpy as np
import oemof.solph as solph
import pandas as pd
from h2pp.oemof_visio_energy_system_graph import ESGraphRenderer

import h2pp.generators
import h2pp.strompreise
from h2pp.generators import (create_electrolyzer, create_fuel_cell_chp, create_h2_storage, convert_kg_H2_to_kWh,
                             create_compressor_a,
                             create_simple_inverter,
                             Jahreszeit)

def run_simulation(sim_config_dict, jahreszeit: Jahreszeit, p_el: float = None, p_fc: float = None,
                   m_tank: float = None, compress_before_storing: bool = False, c_battery=None,
                   verbose=False,
                   **kwargs):
    """

    Erstellt ein Energiesystem in OEMOF und führt eine Simulation für eine typische Woche der übergebenen Jahreszeit
    durch. OEMOF bestimmt das optimale Betriebsverhalten der Anlage (Energiemärkte, Energiewandler, Speicher), um die
    Energiekosten zu minimieren. Die Energiekosten je Energieträger (bzw. Erlöse beim Verkauf bzw. Einsparung Wärme)
    werden aus dem Optimierungsresultat extrahiert und zurückgegeben (in einem Dict)

    Hinweise:
    - Die Elektrolyseur-, Brennstoffzellenleistung und Tankgröße sowie compress_before_storing werden NICHT aus der
    JSON gelesen, sondern aus den übergebenen Parametern!
    - Alle Leistungen werden prinzipiell in kW verarbeitet.

    @param p_el: Leistung des Elektrolyseurs in kW. None, um den Elektrolyseur auszuschalten.
    @param p_fc: Leistung der Brennstoffzelle in kW. None, um die Brennstoffzelle auszuschalten.
    @param m_tank: max. Masse Wasserstoff im Tank in kg.
    @param compress_before_storing: Angabe, ob das H2 vor dem Speichern komprimiert werden soll.
    @param c_battery: Kapazität der Batterie in kWh. Nur im Batterie-Referenzfall mit einem Wert zu versehen, sonst None
    @param verbose: Ausgabe zusätzlicher Infos (z.B. Abschätzung Peak-Leistung, Jahresbedarf, etc.)
    kwargs:
    @param plot_energy_sytem_graph: bool, ob der Graph des Energiesystems geplottet werden soll.
    @return:

    """

    if compress_before_storing is True and m_tank is None:
        raise ValueError("If compress_before_storing is True, m_tank must be specified!")


    # Intervalle in angegebener Schrittweite.
    # Intervall muss so gewählt werden, dass ganzzahlige Vielfache davon am Ende zu einem Intervall von 0:00 an Tag 1 bis zu 0:00 an Tag 2 führen
    # d.h., das Intervall muss ohne Rest durch 24*60min teilbar sein:

    freq_in_min = sim_config_dict["base_sim_interval"]

    if (24*60) % freq_in_min != 0:
        raise ValueError(f"Base simulation interval {freq_in_min} is not a divisor of 24*60 minutes!")


    # Simulate 7 full days plus 0:00 of the first day of the consecutive week (last interval was especially needed for the
    # interpolation, see there)
    # the concrete selected day does not matter here. it is only important that the length and frequency are correct.
    my_index = pd.date_range(start='2020-01-01',
                             end='2020-01-08',
                             inclusive='both',  # Include both dates -> last interval step is 08. Jan 2020 00:00
                             freq=f"{freq_in_min}min")

    # Nutze diesen Index, um das Energiesystem zu erstellen
    my_energysystem = solph.EnergySystem(timeindex=my_index, infer_last_interval=True)

    # Buses definieren und hinzufügen
    bel_ac = solph.buses.Bus(label='electricity_ac')
    bel_dc = solph.buses.Bus(label='electricity_dc')
    bth = solph.buses.Bus(label="thermal")
    bhydr_30 = solph.buses.Bus(label="h2_30bar")
    bhydr_50 = solph.buses.Bus(label="h2_50bar") # für die Vorverdichtung, nicht anderes.
    bhydr_350 = solph.buses.Bus(label="h2_350bar")
    bhydr_350_from_compressor = solph.buses.Bus(label="h2_350bar_from_compressor") # ONLY the output from the compressor. to prevent "buying the H2 from a hydrogen refueling station and compressing it cheap to 700 bar"
    bhydr_700 = solph.buses.Bus(label="h2_700bar")

    my_energysystem.add(bel_ac, bel_dc, bhydr_30, bhydr_50, bhydr_350, bhydr_350_from_compressor, bhydr_700, bth)


    # ===== Erzeuger =====

    # Initialize the time series for the producers of electricity and hydrogen...
    generator_dc_electricity_ts = sim_config_dict['dc_generators_all_ts'][jahreszeit.name]
    generator_ac_electricity_ts = sim_config_dict['ac_generators_all_ts'][jahreszeit.name]
    generator_hydrogen_ts = sim_config_dict['hydrogen_generators_all_ts'][jahreszeit.name]


    electricity_dc_generators = solph.components.Source(label='Electricity_DC_Generation_Ges', outputs={bel_dc: solph.Flow(
        fix=generator_dc_electricity_ts, nominal_value=1
        # nominal_value (erforderlich) überall auf 1, da timeseries bereits skaliert und wir alle Flows in eqiv. kW Leistung rechnen
        )})

    electricity_ac_generators = solph.components.Source(label='Electricity_AC_Generation_Ges',
                                                        outputs={bel_ac: solph.Flow(
                                                            fix=generator_ac_electricity_ts, nominal_value=1
                                                        )})

    # Generator for Hydrogen - currently only for 30 bar as I currently see no real use cases where we directly get higher pressured hydrogen from a source other than via the market
    h2_generators = solph.components.Source(label='H2_Generation_Ges', outputs={bhydr_30: solph.Flow(
        fix=generator_hydrogen_ts, nominal_value=1
    )})

    my_energysystem.add(electricity_ac_generators, electricity_dc_generators, h2_generators)

    # ==================


    # === VERBRAUCHER ===
    consumed_ac_electricity_ts = sim_config_dict['ac_consumers_all_ts'][jahreszeit.name]
    consumed_dc_electricity_ts = sim_config_dict['dc_consumers_all_ts'][jahreszeit.name]
    consumed_hydrogen_700_ts = sim_config_dict['hydrogen_consumers_700_all_ts'][jahreszeit.name]
    consumed_hydrogen_350_ts = sim_config_dict['hydrogen_consumers_350_all_ts'][jahreszeit.name]


    electricity_consumers_ac = solph.components.Sink(label='Electricity_Consumption_AC_Ges', inputs={bel_ac: solph.Flow(
        fix=consumed_ac_electricity_ts, nominal_value=1
    )})

    electricity_consumers_dc = solph.components.Sink(label='Electricity_Consumption_DC_Ges',
                                                       inputs={bel_dc: solph.Flow(
                                                           fix=consumed_dc_electricity_ts, nominal_value=1
                                                       )})

    h2_consumers_700 = solph.components.Sink(label='H2_Consumption_Ges_700', inputs={bhydr_700: solph.Flow(
        fix=consumed_hydrogen_700_ts, nominal_value=1
    )})

    h2_consumers_350 = solph.components.Sink(label='H2_Consumption_Ges_350', inputs={bhydr_350: solph.Flow(
        fix=consumed_hydrogen_350_ts, nominal_value=1
    )})

    my_energysystem.add(electricity_consumers_dc, electricity_consumers_ac, h2_consumers_350, h2_consumers_700)

    # ==================

    # Only add the components that were not disabled in the function call (p_el, p_fc, m_tank, c_battery)
    # Elektrolyseur
    if p_el is not None:
        eta_elektrolyseur = sim_config_dict["electrolyzer"]["efficiency"]
        my_energysystem.add(create_electrolyzer(input_bus_el=bel_dc,
                                                output_bus_h2=bhydr_30,
                                                electrical_efficiency=eta_elektrolyseur,
                                                nominal_power=p_el))

    # Brennstoffzelle
    if p_fc is not None:
        # Kraft-Wärme-Kopplung / BHKW: CHP (Combined Heat and Power)
        eta_fc_el = sim_config_dict["fuelcell"]["efficiency_electric"]
        eta_fc_th = sim_config_dict["fuelcell"]["efficiency_thermal"]
        my_energysystem.add(create_fuel_cell_chp(input_bus_h2=bhydr_30,
                                                 output_bus_el=bel_dc,
                                                 output_bus_th=bth,
                                                 electrical_efficiency=eta_fc_el,
                                                 thermal_efficiency=eta_fc_th,
                                                 nominal_power_el=p_fc))

    # Batterie
    if c_battery is not None:
        my_energysystem.add(
            h2pp.generators.create_battery_storage(bus_el=bel_dc, storage_capacity_in_kWh=c_battery,
                                                   soc_min=sim_config_dict["battery"]["soc_min"],
                                                   soc_max=sim_config_dict["battery"]["soc_max"]))


    # ===========================

    # Verdichter zum Vertanken - hier zunächst mit elektrischem (AC) Input als Verdichteraufwand angenommen

    # Vereinfachung: Keine detaillierte Modellierung des kaskadierten Hochdruckspeichersystems, da davon ausgegangen
    # wird, dass diese nur als Zwischenspeicher dienen und demnach bezogen auf das konkrete Tankverhalten keinen
    # Unterschied machen, solange der Verdichterdurchsatz (kg/h) korrekt gewählt ist

    # Prüfen, ob Angleichung des Tankniveaus zwischen Simulationsstart und -endzeitpunkt gewünscht ist
    balance_storage_level = False
    if "tank" in sim_config_dict:
        if "balance_storage_level" not in sim_config_dict["tank"]:
            raise ValueError("Please specify 'balance_storage_level' (true/false) in the JSON!")

        balance_storage_level = sim_config_dict["tank"]["balance_storage_level"]


    # Modellierung von Wasserstofftank und Verdichtung bis 350 bar - allerdings davon abhängig, ob Vorverdichtet werden soll oder nicht
    if compress_before_storing:
        prop_factor_50bar = sim_config_dict["tank"]["density_prop_factor_h2_50bar_to_30bar"] # how many more kgs can we store with the same volume but higher pressure of 50 bar?

        # Auch ohne "stationären Tank" haben wir den FCEV Verdichter // FCEV Tank

        # If the 50bar Tank is used, we need to compress STARTING FROM THESE 50 BAR. This gives a different energy demand for compression

        # get energy demand from 50 -> 950 bar
        cmpr_energy = (sim_config_dict["HRS_Compressor"]["work_30_to_950_bar_in_kWh_per_kg"]
                       - sim_config_dict["HRS_Compressor"]["work_30_to_50_bar_in_kWh_per_kg"])

        # This one holds the energy demand for compression from 50 to 350 bar (incl. higher pressure due to slight losses)
        cmpr_energy_to_350plus_only = cmpr_energy - sim_config_dict["HRS_Compressor"]["work_350_to_700_bar_in_kWh_per_kg"]


        my_energysystem.add(create_compressor_a(input_bus_h2=bhydr_50, output_bus_h2=bhydr_350_from_compressor,
                                                electrical_bus=bel_ac,
                                                compression_energy_kwh_per_kg=cmpr_energy_to_350plus_only,
                                                nominal_power_in_kg_per_h=sim_config_dict["HRS_Compressor"][
                                                    "throughput_kg_per_hour"],
                                                label="H2_Compressor_50_to_350"))

        # technically, compress_before_storing=True implies that we have a (50 bar) tank. As we already do an error handling in the beginning, we dont need to check here whether m_tank is None (it CANNOT be None here)

        # get 30->50bar compressor throughput from the config
        nominal_power_kg_per_h = sim_config_dict["tank"]["throughput_50bar_compressor_kg_per_hour"]

        my_energysystem.add(create_compressor_a(input_bus_h2=bhydr_30, output_bus_h2=bhydr_50,
                                                electrical_bus=bel_ac, compression_energy_kwh_per_kg=sim_config_dict["HRS_Compressor"]["work_30_to_50_bar_in_kWh_per_kg"],
                                                nominal_power_in_kg_per_h=nominal_power_kg_per_h,
                                                label="H2_Compressor_30_to_50"))


        # we also need the "Way back" (expansion) to 30 bar for the fuel cell
        my_energysystem.add(create_compressor_a(input_bus_h2=bhydr_50, output_bus_h2=bhydr_30,
                                                electrical_bus=bel_ac, compression_energy_kwh_per_kg=sim_config_dict["HRS_Compressor"]["work_50_to_30_bar_in_kWh_per_kg"],
                                                nominal_power_in_kg_per_h=nominal_power_kg_per_h,
                                                label="H2_Compressor_50_to_30"))

        # Tank muss am 50 bar Bus hängen (vorverdichtet)
        my_energysystem.add(create_h2_storage(bus_h2=bhydr_50, storage_capacity_in_kg=m_tank * prop_factor_50bar,
                                              balance_storage_level=balance_storage_level))



    else:
        # Keine Vorverdichtung.
        # This one holds the energy demand for compression from now -> 30 <- to 350 bar (incl. higher pressure due to slight losses)
        cmpr_energy_to_350plus_only = (sim_config_dict["HRS_Compressor"]["work_30_to_950_bar_in_kWh_per_kg"]
                                       - sim_config_dict["HRS_Compressor"]["work_350_to_700_bar_in_kWh_per_kg"])

        my_energysystem.add(create_compressor_a(input_bus_h2=bhydr_30, output_bus_h2=bhydr_350_from_compressor,
                                                electrical_bus=bel_ac,
                                                compression_energy_kwh_per_kg=cmpr_energy_to_350plus_only,
                                                nominal_power_in_kg_per_h=sim_config_dict["HRS_Compressor"][
                                                    "throughput_kg_per_hour"],
                                                label="H2_Compressor_30_to_350"))


        # Tank am 30bar bus.
        if m_tank is not None:
            my_energysystem.add(create_h2_storage(bus_h2=bhydr_30, storage_capacity_in_kg=m_tank,
                                                  balance_storage_level=balance_storage_level))

    # 350 to 700 bar compressor regardless of if we have pre compressed the hydrogen or not
    # This one here is "the rest of the compressor pipeline". The energy demand for compression from 350 to 700 bar (last step)
    # as we already compressed a bit higher than 350 bar in the previous step, this also has the "slight higher pressure" included in the end.
    my_energysystem.add(create_compressor_a(input_bus_h2=bhydr_350_from_compressor, output_bus_h2=bhydr_700,
                                            electrical_bus=bel_ac,
                                            compression_energy_kwh_per_kg=sim_config_dict["HRS_Compressor"][
                                                "work_350_to_700_bar_in_kWh_per_kg"],
                                            nominal_power_in_kg_per_h=sim_config_dict["HRS_Compressor"][
                                                "throughput_kg_per_hour"],
                                            label="H2_Compressor_350_to_700"))

    # finally, we need to transform the "350bar from compressor" to the "normal" 350 bar bus
    # the only reason for doing this is to prevent that "hydrogen bought at 350bar from the grid gets fed into the compressor
    # for cheap compression to 700 bar" (in reality, it is directly taken from the refueling station at the corresponding pressure
    # in the reference case.)

    my_energysystem.add(solph.components.Converter(
        label="H2_350_from_compressor_to_350",
        inputs={bhydr_350_from_compressor: solph.Flow()},
        outputs={bhydr_350: solph.Flow()}))

    # Inverter fur AC/DC
    inv_eff = sim_config_dict["inverter_efficiency"]
    my_energysystem.add(create_simple_inverter(input_bus=bel_ac, output_bus=bel_dc, efficiency=inv_eff, label='Inverter_AC_DC'))
    my_energysystem.add(create_simple_inverter(input_bus=bel_dc, output_bus=bel_ac, efficiency=inv_eff, label='Inverter_DC_AC'))


    # TODO Zur Erweitung auf Use Cases wo kein H2 Markt existieren soll: schauen, wie der H2 Markt ausgeschaltet
    #  werden kann, ohne Infeasibilities zu erzeugen

    # ===== Hydrogen Market =====
    if 'h2_price_per_kg_350bar' not in sim_config_dict:
        raise ValueError("No hydrogen price for 350 bar (h2_price_per_kg_350bar) specified in JSON file!")

    price_h2_per_kg_350 = sim_config_dict['h2_price_per_kg_350bar']
    price_h2_per_equiv_kWh_350 = price_h2_per_kg_350 / convert_kg_H2_to_kWh(
        1)  # kWh pro kg H2 (etwa 33.3) -> H2_PRICE per kg durch das teilen -> EUR / kWh

    # Aus dem fixen Preis eine Zeitreihe richtiger Länge mit konstantem Wert erstellen
    var_costs_s_h2_grid_buy_350 = [price_h2_per_equiv_kWh_350]*((24*60*7)//freq_in_min + 1)

    s_h2_grid_buy_350 = solph.components.Source(
        label="s_h2_grid_buy_350",
        outputs={
            bhydr_350: solph.Flow(
                variable_costs=var_costs_s_h2_grid_buy_350)})

    if 'h2_price_per_kg_700bar' not in sim_config_dict:
        raise ValueError("No hydrogen price for 700 bar (h2_price_per_kg_700bar) specified in JSON file!")

    price_h2_per_kg_700 = sim_config_dict['h2_price_per_kg_700bar']
    price_h2_per_equiv_kWh_700 = price_h2_per_kg_700 / convert_kg_H2_to_kWh(
        1)  # kWh pro kg H2 (etwa 33.3) -> H2_PRICE per kg durch das teilen -> EUR / kWh

    var_costs_s_h2_grid_buy_700 = [price_h2_per_equiv_kWh_700]*((24*60*7)//freq_in_min + 1)

    s_h2_grid_buy_700 = solph.components.Source(
        label="s_h2_grid_buy_700",
        outputs={
            bhydr_700: solph.Flow(
                variable_costs=var_costs_s_h2_grid_buy_700)})


    # Zusammenstellung Marktpreise

    # 1. Abschätzung Jahresbedarf und Spitzenlast
    jahresbedarf_abschaetzung = sim_config_dict["jahresbedarf_abschaetzung_fuer_strompreis"]
    peak_abschaetzung = sim_config_dict["peak_abschaetzung_fuer_strompreis"]
    peak_abschaetzung += (p_el / eta_elektrolyseur) if p_el is not None else 0 # mehr ist als Peak nicht möglich: Max. Lokaler Bedarf + Betrieb elektrolyseur zur H2 Produktion (Eingangsleistung!) (+ Verdichter s.u.)

    leistung_verdichter_kW = sim_config_dict["HRS_Compressor"]["throughput_kg_per_hour"] * sim_config_dict["HRS_Compressor"]["work_30_to_950_bar_in_kWh_per_kg"] # (kg/h * kWh/kg) = kWh/h = kW
    peak_abschaetzung += leistung_verdichter_kW if not (p_el is None and m_tank is None) else 0 # Assumption that HRS is present (cf. calculate_tco with same thoughts)
    if verbose:
        print("Geschätzter Peak: ", peak_abschaetzung, "kW")
        print("Geschätzter Jahresbedarf: ", jahresbedarf_abschaetzung, "kWh")

    # If the "hack" variable "strombezug_begrenzen" is set to True, we limit the maximum power that can be bought from the grid to the peak power needed to archieve Jahresbenutzungsdauer > 2500
    if "strombezug_begrenzen" in sim_config_dict:
        if sim_config_dict["strombezug_begrenzen"]:
            warnings.warn("The experimental feature strombezug_begrenzen=true was used.")
            warnings.warn(
                "Maximum power draw from grid is limited to the power needed to fall above the 2500h/a threshold. Note that this might lead to infeasiblities!")
            # How high is the peak allowed to be in order to not exceed the 2500h/a threshold?
            # plus 10% puffer
            # setze peak_abschaetzung auf diesen wert, damit wir auch die richtigen kosten direkt bekommen.
            peak_abschaetzung = 0.9 * (jahresbedarf_abschaetzung / 2500)


    steuern_umlagen_schaetzung = h2pp.strompreise.stromkosten_2024(jahresverbrauch_in_kWh=jahresbedarf_abschaetzung,
                                                                   peak_leistung_in_kW=peak_abschaetzung,
                                                                   spannungsebene=h2pp.strompreise.Spannungsebene[ sim_config_dict["spannungsebene"]],
                                                                   ort=sim_config_dict["ort"],
                                                                   kat_konzession=sim_config_dict["kat_konzession"]
                                                                   )

    if "nur_beschaffungskosten" in sim_config_dict:
        if sim_config_dict["nur_beschaffungskosten"]:
            warnings.warn("Netzentgelte, Umlagen usw werden ignoriert!")
            steuern_umlagen_schaetzung = 0.0

    if "aufschlag_strom_manuell_ct" in sim_config_dict:
        steuern_umlagen_schaetzung = sim_config_dict["aufschlag_strom_manuell_ct"] / 100


    if verbose:
        print("Abschätzung der Aufschläge auf den Spotmarkpreis: ", steuern_umlagen_schaetzung, " EUR/kWh")

    spot_price = sim_config_dict['electricity_market_base_price_ts'][jahreszeit.name]
    var_costs_s_electric_grid_buy = spot_price + steuern_umlagen_schaetzung

    # TODO: Currently, our simulation seems to be unable to handle negative power prices correctly. Therefore,
    #  we MUST strip them to 0.0. This partially leads to a bit strange behaviour that should be investigated.
    #  (see Thesis JC for Example)
    # First check if such points occur and warn the user.
    if np.any(var_costs_s_electric_grid_buy < 0):
        warnings.warn("Negative power prices detected (buying from grid). These will be set to 0.0 to prevent infeasibilities.")
        var_costs_s_electric_grid_buy[var_costs_s_electric_grid_buy < 0] = 0.0

    abzugbetrag_strom = sim_config_dict["abzugbetrag_strom_in_ct"] / 100  # EUR / kWh
    var_costs_s_electric_grid_sell = spot_price - abzugbetrag_strom

    # Für "negativen Ertrag" beim Kaufen auch eine Warnung da lassen..
    if np.any(var_costs_s_electric_grid_sell < 0):
        warnings.warn("Negative power prices detected (selling to grid). Although the simulation should still function as intended ('penalized for selling'), the results should be interpreted with caution.")


    # Markt Kauf:

    the_flow = solph.Flow(variable_costs=var_costs_s_electric_grid_buy)

    if "strombezug_begrenzen" in sim_config_dict:
        if sim_config_dict["strombezug_begrenzen"]:
            # mit peak_abschaetzung von oben so begrenzt, dass wir mutmasslich unter den 2500 h/a landen würden
            the_flow = solph.Flow(variable_costs=var_costs_s_electric_grid_buy, nominal_value=peak_abschaetzung)

            if verbose:
                print("Strombezug auf ", peak_abschaetzung, "kW begrenzt.")


    s_electric_grid_buy = solph.components.Source(
        label="s_el_grid_buy",
        outputs={
            bel_ac: the_flow}) # here, the_flow is now either the limited flow (strombezug_begrenzen) or the normal flow


    # Markt Verkauf:

    # Hinweis: Es muss stets der absolute Kaufpreis niedriger als der Verkaufspreis sein, sonst würde ein unbegrenzter
    # Bezug von Energie aus dem Stromnetz & direkter Verkauf als Optimum gesehen werden und damit das Programm crashen! (Infeasible)
    # (mit dem verwendeten Preismodell ist dies zunächst eh nie der Fall, sollte aber in Erinnerung behalten werden)

    var_cost_s_electric_grid_sell = -1 * var_costs_s_electric_grid_sell # Minus ist wichtig! (Verkaufserlös, negative Kosten)
    s_electric_grid_sell = solph.components.Sink(
        label="s_el_grid_sell",
        inputs={
            bel_ac: solph.Flow(
                variable_costs=var_cost_s_electric_grid_sell)})


    # === HEAT ===
    HEAT_PRICE_PER_KWH = sim_config_dict["heat_price_per_kWh"]
    # das oben soll die "Einkaufskosten" die eigentlich für Wärme entstehen, darstellen; also hier quasi "Einsparung" als "Einnahme" dargestellt
    var_cost_s_save_heat = [-1*HEAT_PRICE_PER_KWH] * ((24 * 60 * 7) // freq_in_min + 1) # Minus => "Verkauf"
    s_save_heat = solph.components.Sink(
        label="s_save_heat",
        inputs={
            bth: solph.Flow(
                variable_costs=var_cost_s_save_heat)})

    my_energysystem.add(s_electric_grid_buy, s_h2_grid_buy_350, s_h2_grid_buy_700, s_electric_grid_sell, s_save_heat)


    # == Energiesystem plotten ==
    # Needs graphviz installed to work

    if 'plot_energy_sytem_graph' in kwargs:
        if kwargs['plot_energy_sytem_graph']:
            gr = ESGraphRenderer(energy_system=my_energysystem, filepath="../energy_system", img_format="pdf")
            gr.view()

    # ===========================

    # initialise operational model (create problem)
    om = solph.Model(my_energysystem)

    # set tee to True to get solver output
    om.solve(solver='cbc', solve_kwargs={'tee': False})

    # get results
    my_energysystem.results["main"] = solph.processing.results(om)
    my_energysystem.results["meta"] = solph.processing.meta_results(om)

    # define an alias for shorter calls below
    results = my_energysystem.results["main"]

    # Get the cost data for bought energy
    # Leistung zu skalieren auf intervallänge!! Bspw. wenn Intervallänge 15 min, dann wirkt Leistung von 4 Intervallen auf 1h -> zu vierteln vor Summenbildung (kWh)
    # -2 von hinten beim Array: 1. the last entry is always a weird "nan" entry. 2. Moreover, as we simulate one
    # interval "too much" (0:00 day 1 to 0:00 on "day 8" closed interval) we need to omit this penultimate value too,
    # or we would get slightly "too high" energy costs.

    el_grid_buy_seq_power = (freq_in_min / 60) * solph.views.node(results, 's_el_grid_buy')["sequences"].values[:-2, 0]
    el_grid_source_total_cost_spot_price_only = sum(el_grid_buy_seq_power * spot_price[:-1]) # Nur variabler Spotmarktanteil summieren, die restlichen Aufschläge ergeben sich direkt über Jahresverbrauch + Peak (in der TCO Berechnung aufsummiert)

    el_grid_sell_seq_power = (freq_in_min / 60) * solph.views.node(results, 's_el_grid_sell')["sequences"].values[:-2, 0]
    el_grid_sink_total_cost = sum(el_grid_sell_seq_power * var_cost_s_electric_grid_sell[:-1])

    h2_grid_buy_seq_power_350 = (freq_in_min / 60) * solph.views.node(results, 's_h2_grid_buy_350')["sequences"].values[
                                                     :-2, 0]
    h2_grid_source_total_cost_350 = sum(h2_grid_buy_seq_power_350 * var_costs_s_h2_grid_buy_350[:-1])

    h2_grid_buy_seq_power_700 = (freq_in_min / 60) * solph.views.node(results, 's_h2_grid_buy_700')["sequences"].values[:-2, 0]
    h2_grid_source_total_cost_700 = sum(h2_grid_buy_seq_power_700 * var_costs_s_h2_grid_buy_700[:-1])

    h2_grid_source_total_cost = h2_grid_source_total_cost_350 + h2_grid_source_total_cost_700

    heat_grid_sell_seq_power = (freq_in_min / 60) * solph.views.node(results, 's_save_heat')["sequences"].values[:-2, 0]
    heat_grid_sink_total_cost = sum(heat_grid_sell_seq_power * var_cost_s_save_heat[-1])

    if c_battery is not None:
        column_name = (('BatteryStorage', 'None'), 'storage_content')
        SC = solph.views.node(results, 'BatteryStorage')['sequences'][column_name]
        batterie_kwhs = SC.values[:-2] # Wieder wie oben: 1. letzter wert i.A. None, 2. abgeschnitten wegen Simulation von 0:00 an Tag 1 bis 0:00 an Tag 8

        # Normierung auf SOC
        # This will then have values like 0.1 .. 0.9 if SOC_min=0.1 and SOC_max=0.9
        soc_vals = batterie_kwhs / c_battery

        # TODO: Hier könnte noch näher geprüft werden, wieso die SOC values tlw. leicht 0 unterschreiten
        #  (idR nicht mal 1000stel bereich) bzw. ggfs die 1 überschreiten und ob es problematisch ist!
        #  (wenn SOC-Limitierung vorhanden, sollte es eh nicht passieren)
        # Quick Fix: Setze alle Werte unter 0 auf 0 und alle über 1 auf 1.0
        soc_vals[soc_vals < 0] = 0
        soc_vals[soc_vals > 1] = 1

        battery_sequence_soc = soc_vals
    else:
        battery_sequence_soc = None


    # Absichtlich erfolgt der return hier als Dict und nicht OpexParameters Object, da wir später eh noch über die Tage je Jahreszeit summieren müssen!!
    return {
        "el_grid_source_total_cost_spot_price_only": el_grid_source_total_cost_spot_price_only,
        "h2_grid_source_total_cost": h2_grid_source_total_cost,
        "heat_grid_sink_total_cost": heat_grid_sink_total_cost,
        "el_grid_sink_total_cost": el_grid_sink_total_cost,
        "sim_results": results, # needed as we want to plot results later on
        "battery_sequence_soc": battery_sequence_soc,
    }
