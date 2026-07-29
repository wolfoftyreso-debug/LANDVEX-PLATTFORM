"""Integrationer mot externa plattformar (endast stdlib).

Detta lager hör till API-sidan av arkitekturen. Regeln löd länge
"motorkärnan importerar ALDRIG härifrån" — och var osann: revisionen
mätte fyra lata importer vid medvetna sömmar (quiXzoom-adapterns
default-transport, schemaläggarens uppdragsbeställning). En absolut
regel som inte stämmer med koden skyddar ingenting. Den sanna regeln:
motorkärnan når hit ENDAST lazy, vid sömmar som står namngivna med
skäl i `engine/selfaudit.LAYER_SEAMS` — och en onämnd smygväg faller
i självrevisionen i stället för att glida in.
"""
