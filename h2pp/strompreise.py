import enum
from typing import Literal, Tuple


class Spannungsebene(enum.Enum):

    HS = "Hochspannung"
    UHM = "Umspannung Hoch-/Mittelspannung"
    MS = "Mittelspannung"
    UMN = "Umspannung Mittel-/Niederspannung"
    NIS = "Niederspannung"

def leistungspreis(jahresverbrauch_in_kWh: float, peak_leistung_in_kW: float, spannungsebene: Spannungsebene,
                   ort: Literal["BER", "DUS", "DTM"]) -> float:
    '''

    @param jahresverbrauch_in_kWh: Jahresverbrauch in kWh
    @param peak_leistung_in_kW: Höchster aufgetretener Peak im Jahr bzw. erwartete Peak.
    @param spannungsebene: Spannungsebene, an der die Anlage angeschlossen ist.
    @param ort: UN/LOCODE des Ortes. Aktuell sind nur bestimmte Orte implementiert.
    @return: Spezifischer Leistungspreis in EUR/kW für die angegebenen Parameter
    '''

    if ort == "DUS":
        return _netzentgelte_duesseldorf(jahresverbrauch_in_kWh, peak_leistung_in_kW, spannungsebene)[0]
    elif ort == "BER":
        raise NotImplementedError
    elif ort == "DTM":
        return _netzentgelte_dortmund(jahresverbrauch_in_kWh, peak_leistung_in_kW, spannungsebene)[0]
    else:
        raise ValueError("Ort nicht bekannt.")

def _netzentgelte_dortmund(jahresverbrauch_in_kWh: float, peak_leistung_in_kW: float,
                              spannungsebene: Spannungsebene) -> (float, float):
    '''

    Implementiertes Preisblatt für Dortmunder Netz GmbH.
    Quelle: https://do-netz.de/fileadmin/user_upload/Dokumente/PDF/Netzentgelte/Strom/2024/Preisblatt_1_-_Entgelte_fuer_Netznutzung_Strom.pdf

    @param jahresverbrauch_in_kWh: Jahresverbrauch in kWh
    @param peak_leistung_in_kW: Höchster aufgetretener Peak im Jahr bzw. erwartete Peak.
    @param spannungsebene: Spannungsebene, an der die Anlage angeschlossen ist.
    @return: 2-Tupel: Leistungspreis in EUR / kW; Arbeitspreis in ct/kWh.

    '''

    # Jahresverbrauch < 100 000 kWh? (darüber registrierte Leistungsmessung angenommen)
    if jahresverbrauch_in_kWh < 100000:
        return 0, 6.48 # scheinbar kein Leistungspreis
        # Ignoriert wird hier der Grundpreis für Kunden ohne Leistungsmessung (99,50 EUR / a)
    else:
        # Leistungsmessung vorhanden

        # Jahresbenutzungdauer ergibt sich als Quotient aus der im Jahr entnommenen Arbeit in kWh und der zugehörigen
        # Jahreshöchstleistung in kW

        jahresbenutzungsdauer_in_h = jahresverbrauch_in_kWh / peak_leistung_in_kW
        # print("Jahresbenutzungsdauer in h: ", jahresbenutzungsdauer_in_h)
        if jahresbenutzungsdauer_in_h < 2500:
            if spannungsebene == Spannungsebene.HS:
                raise ValueError("Für Dortmund ist dz. kein Arbeitspreis für Hochspannung in den Preisblättern auffindbar. Siehe https://do-netz.de/fileadmin/user_upload/Dokumente/PDF/Netzentgelte/Strom/2024/Preisblatt_1_-_Entgelte_fuer_Netznutzung_Strom.pdf")
            elif spannungsebene == Spannungsebene.UHM:
                return 22.82, 6.68
            elif spannungsebene == Spannungsebene.MS:
                return 23.89, 6.98
            elif spannungsebene == Spannungsebene.UMN:
                return 25.17, 7.43
            elif spannungsebene == Spannungsebene.NIS:
                return 29.71, 7.52
            else:
                raise ValueError("Spannungsebene nicht bekannt")
        else:
            if spannungsebene == Spannungsebene.HS:
                raise ValueError(
                    "Für Dortmund ist dz. kein Arbeitspreis für Hochspannung in den Preisblättern auffindbar. Siehe https://do-netz.de/fileadmin/user_upload/Dokumente/PDF/Netzentgelte/Strom/2024/Preisblatt_1_-_Entgelte_fuer_Netznutzung_Strom.pdf")
            elif spannungsebene == Spannungsebene.UHM:
                return 164.34, 1.02
            elif spannungsebene == Spannungsebene.MS:
                return 150.56, 1.92
            elif spannungsebene == Spannungsebene.UMN:
                return 161.28, 1.99
            elif spannungsebene == Spannungsebene.NIS:
                return 122.46, 3.81
            else:
                raise ValueError("Spannungsebene nicht bekannt")



def _netzentgelte_duesseldorf(jahresverbrauch_in_kWh: float, peak_leistung_in_kW: float,
                              spannungsebene: Spannungsebene) -> (float, float):
    '''

    Implementiertes Preisblatt für Netzgesellschaft Düsseldorf mbH.
    Quelle: https://netz-duesseldorf.de/media/mam-upload/2023-12-20--preisblatt-nne-strom-2024.pdf

    @param jahresverbrauch_in_kWh: Jahresverbrauch in kWh
    @param peak_leistung_in_kW: Höchster aufgetretener Peak im Jahr bzw. erwartete Peak.
    @param spannungsebene: Spannungsebene, an der die Anlage angeschlossen ist.
    @return: 2-Tupel: Leistungspreis in EUR / kW; Arbeitspreis in ct/kWh.
    '''

    # Jahresverbrauch < 100 000 kWh? (darüber registrierte Leistungsmessung angenommen)
    if jahresverbrauch_in_kWh < 100000:
        return 0, 8.27
        # Ignoriert wird hier der Grundpreis für Kunden ohne Leistungsmessung (12,- EUR / a)
    else:
        # Leistungsmessung vorhanden

        # Jahresbenutzungdauer ergibt sich als Quotient aus der im Jahr entnommenen Arbeit in kWh und der zugehörigen Jah-
        # reshöchstleistung in kW

        jahresbenutzungsdauer_in_h = jahresverbrauch_in_kWh / peak_leistung_in_kW
        # print("Jahresbenutzungsdauer in h: ", jahresbenutzungsdauer_in_h)
        if jahresbenutzungsdauer_in_h < 2500:
            if spannungsebene == Spannungsebene.HS:
                return 16.08, 4.15
            elif spannungsebene == Spannungsebene.UHM:
                return 16.40, 5.65
            elif spannungsebene == Spannungsebene.MS:
                return 18.54, 5.70
            elif spannungsebene == Spannungsebene.UMN:
                return 16.15, 6.55
            elif spannungsebene == Spannungsebene.NIS:
                return 19.49, 6.53
            else:
                raise ValueError("Spannungsebene nicht bekannt")
        else:
            if spannungsebene == Spannungsebene.HS:
                return 103.63, 0.65
            elif spannungsebene == Spannungsebene.UHM:
                return 143.39, 0.57
            elif spannungsebene == Spannungsebene.MS:
                return 119.61, 1.66
            elif spannungsebene == Spannungsebene.UMN:
                return 145.88, 1.36
            elif spannungsebene == Spannungsebene.NIS:
                return 89.99, 3.71
            else:
                raise ValueError("Spannungsebene nicht bekannt")


def stromkosten_2024(jahresverbrauch_in_kWh: float,
                     peak_leistung_in_kW: float,
                     spannungsebene: Spannungsebene,
                     ort: Literal["BER", "DUS", "DTM"],
                     kat_konzession: Literal["TK_SL", "TK", "SVK"],
                     marge_in_ct: float = 3,
                     ) -> float:

    '''

    Bestimmung der festen und variablen Stromkosten für Deutschland/den gegebenen Ort der Abnahme im Jahr 2024,
    ohne weitere Vergünstigungen; ohne den Börsenstrompreis, für die gegebenen Einflussparameter.

    @param jahresverbrauch_in_kWh: Jahresverbrauch in kWh
    @param peak_leistung_in_kW: Der höchste aufgetretene Peak im Jahr bzw. erwartete Peak.
    @param kat_konzession: Kundenkategorie für Berechnung der Konzessionsabgabe. TK_SL für Tarifkunde schwachlast, TK für Tarifkunde, SVK für Sondervertragskunde
    @param marge_in_ct: Höhe der Marge des Versorgers/Lieferanten, in ct/kWh. Typischerweise was zwischen 1 und 5 ct
    @param ort: UN/LOCODE des Ortes, für den die Stromkosten berechnet werden sollen. Aktuell sind nur bestimmte Orte implementiert.
    @return:
    Summe aller Stromkosten in EUR/kWh, ohne den Variablen Marktpreis (Anteil "Beschaffung & Vertrieb"), Messstellenbetrieb und den Leistungspreis der Netzentgelte (Euro/kW des höchsten Peaks)

    '''

    if kat_konzession not in ["TK_SL", "TK", "SVK"]:
        raise ValueError("Kategorie für Konzessionsabgabe nicht bekannt. Mögliche Werte sind: TK_SL (Tarifkunde Schwachlast), TK (Tarifkunde) oder SVK (Sondervertragskunde), aber übergeben wurde: ", kat_konzession)


    # Preise in EUR am Ende. Weil aber meist überall von ct/kWh gesprochen wird, rechnen wir erst in ct und am ende /100
    preis_add = 0

    # 1. Steuern
    preis_add += 2.05  # 1.1 Stromsteuer
    preis_add += 0.0  # 1.2 Mehrwertsteuer entfällt für Industriekunden

    # 1.3 Konzessionsabgabe https://www.gesetze-im-internet.de/kav/BJNR000120992.html
    # gemeindegroesse_in_tsd_einwohner: Größe der Gemeinde, in der das System sich befindet. Bspw. bei 1000 Einwohnern wäre der Wert 1.

    if ort == "BER":
        gemeindegroesse_in_tsd_einwohner = 3645
    elif ort == "DUS":
        gemeindegroesse_in_tsd_einwohner = 619

    elif ort == "DTM":
        gemeindegroesse_in_tsd_einwohner = 595

    # ===

    if kat_konzession == "TK_SL": # Tarifkunde Schwachlast
        preis_add += 0.61
    elif kat_konzession == "SVK": # Sondervertragskunde
        preis_add += 0.11
    else:

        if gemeindegroesse_in_tsd_einwohner < 25:
            preis_add += 1.32
        elif gemeindegroesse_in_tsd_einwohner < 100:
            preis_add += 1.59
        elif gemeindegroesse_in_tsd_einwohner < 500:
            preis_add += 1.99
        else:
            preis_add += 2.39

    # 2. Umlagen
    preis_add += 0.656  # 2.1 Offshore
    preis_add += 0.275  # 2.2 KWK

    # 2.3 StromNEV
    # Für den Verbrauch unter 1 Mio kWh 0.643 ct/kWh
    # Für den Verbrauch über 1 Mio kWh 0.05 ct/kWh
    # Basierend auf dem Jahresverbrauch wird hieraus ein gewichteter Preis pro kWh berechnet
    # nur für Anforderungen in der TCO (Keine Aufteilung auf den Teil über und 1 Mio. EUR), kein Güteverlust
    menge_unter_1e6 = min(jahresverbrauch_in_kWh, 1e6)
    menge_ueber_1e6 = max(0.0, jahresverbrauch_in_kWh - 1e6)

    # print("menge <1e6: ", menge_unter_1e6)
    # print("menge >1e6: ", menge_ueber_1e6)
    if jahresverbrauch_in_kWh == 0:
        # Edge Case, falls kein lokaler elektrischer Verbrauch (bspw. wenn nur H2-Bedarf)
        # Selbst wenn BDEW-Jahresbedarf > 0 hab ich in der GUI tlw. fälle, wo hier der =0 Fall eintritt (vermutlich wenn alles durch lokale Produktion gedeckt)
        anteil_unter_1e6 = 0
        anteil_ueber_1e6 = 0
    else:
        anteil_unter_1e6 = menge_unter_1e6 / jahresverbrauch_in_kWh
        anteil_ueber_1e6 = menge_ueber_1e6 / jahresverbrauch_in_kWh

    preis_add += anteil_unter_1e6 * 0.643
    preis_add += anteil_ueber_1e6 * 0.05

    # 3. Energiebereitstellung
    # 3.1 und 3.2 Beschaffung und Vertrieb => Marktpreis, wird an anderer Stelle aufgeschlagen

    # 3.3 Marge
    preis_add += marge_in_ct

    # 4. Infrastrukturkosten

    # 4.1 Netzentgelte
    # Nicht bilanziert: Leistungspreis [Euro/kW]
    # erfolgt erst NACH Bilanzierung der variablen Stromkosten pro kWh

    # Regional unterschiedlich. Hier können weitere Orte hinzugefügt werden
    if ort == "DUS":
        preis_add += _netzentgelte_duesseldorf(jahresverbrauch_in_kWh=jahresverbrauch_in_kWh,
                                               peak_leistung_in_kW=peak_leistung_in_kW, spannungsebene=spannungsebene)[1]
    elif ort == "BER":
        raise NotImplementedError

    elif ort == "DTM":
        preis_add += _netzentgelte_dortmund(jahresverbrauch_in_kWh=jahresverbrauch_in_kWh,
                                               peak_leistung_in_kW=peak_leistung_in_kW, spannungsebene=spannungsebene)[1]

    else:
        raise ValueError(f"Für den {ort} sind keine Netzentgelte hinterlegt.")

    # 4.2 Messung & Messstellenbetrieb
    # Annahme: Kosten vergleichsweise klein oder über die Netzentgelte mit abgerechnet, daher hier vorerst rausgelassen.
    # Müsste vermutlich eh "je Zählstelle" bilanziert werden und nicht über den Strompreis.

    return preis_add / 100  # EUR/kWh

