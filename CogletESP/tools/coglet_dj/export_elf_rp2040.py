"""Export the Elf choreography (choreo_elf.py) to RP2040/dance_elf.py.

python3 export_elf_rp2040.py <path/to/RP2040/dance_elf.py>
"""
import sys

import export_xmas_rp2040

if __name__ == "__main__":
    export_xmas_rp2040.main(sys.argv[1], prefix="elf", names=("workshop", "mischief", "party"), edition="Elf")
