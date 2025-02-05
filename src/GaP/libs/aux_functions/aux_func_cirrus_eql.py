"""
Auxiliary functions for creating EQUILIBRATION sections in CIRRUS input files.
"""


def setup_equilibration(name, d_datum, pressure, wgc_d, rtempvd, top, bottom):
    """
    Provisional function to create EQUILIBRATION sections in CIRRUS input files.
    """
    wgc_d_line = f"  WGC_D {wgc_d} m\n" if wgc_d is not None else ""
    equil_str = f"""
EQUILIBRATION {name}
  DATUM_D {d_datum} m
  PRESSURE {pressure:.2f} Bar
  {wgc_d_line}
  TEMPERATURE_TABLE
    D_UNITS m !cannot be otherwise
    TEMPERATURE_UNITS C !cannot be otherwise
    {rtempvd}
  /
  END
  
  SALT_TABLE
    D_UNITS m
    CONCENTRATION_UNITS MOLE
    SALTVD
      {top} 0.032
      {bottom} 0.032
    /
  END
  GAS_IN_LIQUID_MOLE_FRACTION 0.0
/
"""
    equil_lines = [line.rstrip() + '\n' for line in equil_str.strip().split('\n')]
    return equil_lines

