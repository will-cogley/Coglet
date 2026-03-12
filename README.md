# Coglet
Will Cogley's DIY Desktop Companion for Makers

# Instructions
Coming Soon, for now refer to the translated docs for how to upload to the ESP.

# Known Issues
PCB (CogNog V1.0):
- USB socket for RP2040 is tight - requires a slim USB-C cable
- ESP Camera socket too close to other components
- In general needs more bulk capacitance to manage power dips
- Mic socket too close to ESP
- Camera will not work with default pins and simultaneously use tasks requiring PSRAM - must rewire the following ESP pins and use camera-version branch of CogletESP
- 35->14
- 36->41
- 37->42
- Mouth pin is on pin 19 - the final slot - which is unintuitive
- Camera feed for ESP32 Cam is horizontally flipped!
