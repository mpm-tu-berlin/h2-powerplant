from oemof import solph
from h2pp.generators import (create_pv_plant_time_series, Jahreszeit, BDEW_Kundengruppe,
                             BDEW_Tagesart, __import_bdew_values__)


if __name__ == "__main__":
    bel = solph.buses.Bus(label='electricity')

    a = create_pv_plant_time_series(latitude=37.77, longitude=-122.419,
                                    jahreszeit=Jahreszeit.UEBERGANG,
                                    peakpower_in_kW=1.0 * 1e3,
                                    # in Anlehnung an zu installierende Leistung EUREF Campus Düsseldorf
                                    surface_tilt=0,
                                    surface_azimuth=180,
                                    base_sim_interval_in_min=15,
                                    sim_sow=0
                                    # todo hier später 2x PV draus machen und Zaun + FLoating trennen
                                    )

    a2 = solph.components.Source(label='PV_Floating', outputs={bel: solph.Flow(fix=a, nominal_value=1)})

    print(__import_bdew_values__(BDEW_Kundengruppe.H0, BDEW_Tagesart.WERKTAG, Jahreszeit.WINTER, 1000))
    print(__import_bdew_values__(BDEW_Kundengruppe.G0, BDEW_Tagesart.SAMSTAG, Jahreszeit.SOMMER, 1000))
    print(__import_bdew_values__(BDEW_Kundengruppe.G1, BDEW_Tagesart.SONNTAG, Jahreszeit.UEBERGANG, 1000))
    print(__import_bdew_values__(BDEW_Kundengruppe.G1, BDEW_Tagesart.SONNTAG, Jahreszeit.UEBERGANG, 2000))
