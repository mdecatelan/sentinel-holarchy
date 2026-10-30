# 🛠️ Bio-Drum 60L Prototype: Clamart Workshop Build Manual

## 1. Overview
This manual provides the complete Bill of Materials (BOM), mechanical adaptations, sensor wiring, and operational safety instructions for the pilot unit constructed in the Clamart workshop.

```
                      ┌─────────────────────────────────┐
                      │    BIO-DRUM 60L PILOT SCHEMATIC │
                      └────────────────┬────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
       [ ROTATING DRUM ]                              [ CONTROL BOX ]
  - Inox 304 Drum (60L)                         - ESP32-WROOM NodeMCU
  - 100 µm Filter Sleeve                        - 4-Channel SSR Module
  - Belt Drive + Inverter Motor                 - BNC pH & ORP Boards
  - Food-Grade Silicone Gaskets                 - DS18B20 1-Wire Temp
                │                                             │
                └──────────────────────┬──────────────────────┘
                                       ▼
                              [ FLUIDIC SYSTEM ]
                        - 12V Aeration Diaphragm Pump
                        - Ceramic Micro-Bubble Diffuser
                        - Inox Solenoid Valves (Transfer/Drain)
```

---

## 2. Bill of Materials (BOM) & Sourcing Budget

| Category | Component Description | Sourcing / Model | Est. Cost (€) |
| :--- | :--- | :--- | :--- |
| **Mechanical** | Stainless Steel Washing Machine Drum & Tub (50–60L) | Upcycled appliance (Ressourcerie / Leboncoin) | 35.00 € |
| **Mechanical** | Stainless Steel Wire Mesh Sleeve (100 µm, 316 Inox) | Metal weaving supplier / AliExpress | 28.00 € |
| **Mechanical** | Food-Grade High-Temp Silicone Gasket (Ø 350 mm) | Industrial seal distributor | 18.00 € |
| **Electronics** | ESP32-WROOM-32 Development Board | Standard retailer | 6.50 € |
| **Electronics** | 4-Channel Solid-State Relay (SSR) Board (250V / 2A) | Electronics retailer | 12.00 € |
| **Sensors** | Industrial Composite pH Probe with BNC Amplifier | DFRobot / Analog pH meter kit | 38.00 € |
| **Sensors** | Platinum ORP / Redox Probe with BNC Interface | DFRobot / Gravity ORP | 45.00 € |
| **Sensors** | DS18B20 Waterproof Stainless Steel Temperature Probe | Dallas 1-Wire probe | 4.50 € |
| **Sensors** | Optical Encoder / Hall Effect Tachometer | 5V pulse sensor | 6.00 € |
| **Actuators** | 12V DC Diaphragm Air Pump (35 W, 45 L/min) | Aquarium aeration pump | 32.00 € |
| **Actuators** | Flexible Silicone Heating Mat (200W, 230V) | 3D printer bed heater | 22.00 € |
| **Actuators** | Food-Grade 1/2" Stainless Steel Solenoid Valves (x2) | Normally closed 12V DC | 34.00 € |
| **Total** | **Complete Hardware Cost for Bio-Drum 60L** | — | **~ 291.00 €** |

---

## 3. Electrical & Sensor Pinout (ESP32)

| ESP32 Pin | Function | Electrical Standard | Destination |
| :--- | :--- | :--- | :--- |
| **GPIO 34** | Analog pH Reading | 0 – 3.3V (ADC1_CH6) | BNC pH Amplifier Output |
| **GPIO 35** | Analog ORP Reading | 0 – 3.3V (ADC1_CH7) | BNC ORP Amplifier Output |
| **GPIO 4** | Slurry Temperature | 1-Wire Digital (4.7k pull-up) | DS18B20 Temp Sensor |
| **GPIO 18** | Drum RPM Counting | Digital Pulse (Falling Edge) | Optical Wheel Encoder |
| **GPIO 25** | Drum Motor Trigger / PWM | 3.3V Logic -> Optocoupler | Motor Inverter Controller |
| **GPIO 26** | Aeration Diaphragm Pump | 3.3V Logic -> Relay IN1 | 12V Air Pump Relay |
| **GPIO 27** | Thermal Mat Heating | 3.3V Logic -> Relay IN2 | 230V SSR Heating Loop |
| **GPIO 32** | VFA Transfer Valve | 3.3V Logic -> Relay IN3 | 12V Solenoid Valve 1 |
| **GPIO 33** | Slurry Drain Valve | 3.3V Logic -> Relay IN4 | 12V Solenoid Valve 2 |

---

## 4. Physical 72-Hour Operation Sequence

1. **Hour 0:00 – Maceration & Inoculation**
   - Introduce 15 kg household waste (peels, starches) + 30L dechlorinated water + 600g crushed eggshells.
   - Run drum at 45 RPM for 45 minutes to homogenize slurry.
   - Temperature setpoint: 28°C.
2. **Hour 1:00 to 36:00 – Acidogenesis Rest**
   - Slow intermittent rotation (8 RPM, 1 minute every 15 minutes).
   - Slurry stabilizes at pH 5.5 – 5.8.
   - Check odor: pleasant lactic/acetic aroma (no putrefaction).
3. **Hour 36:00 – Centrifugal Separation**
   - Accelerate drum to 650 RPM for 15 minutes.
   - Solid fraction (Grade C) stays inside 100 µm mesh.
   - Liquid VFA broth (Grade B precursor) is expelled through valve GPIO 32 into secondary aeration vessel.
4. **Hour 36:00 to 72:00 – Aeration & PHA Feast/Famine**
   - Activate 45 L/min air pump (GPIO 26).
   - Add 200 mL compost inoculum extract.
   - Dissolved oxygen maintained > 2 mg/L.
   - Slurry turns milky-opalescent as bacteria accumulate PHA granules.
5. **Hour 72:00 – Thermal Harvest & Separation**
   - Brief thermal pasteurization at 70°C for 10 minutes to induce cell autolysis.
   - Centrifuge to recover Grade A PHA pellet and bottle Grade B liquid biostimulant.
