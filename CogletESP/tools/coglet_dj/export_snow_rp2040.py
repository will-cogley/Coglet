"""Export the Snowman choreography (choreo_snow.py) to RP2040/dance_snow.py.

python3 export_snow_rp2040.py <path/to/RP2040/dance_snow.py>
"""
import sys

import export_xmas_rp2040

if __name__ == "__main__":
    export_xmas_rp2040.main(sys.argv[1], prefix="snow", names=("lullaby", "stomp", "blizzard"), edition="Snowman")
