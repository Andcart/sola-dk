from typing import Union

def w_per_sqm_to_kwh_per_sqm(
    irradiance_w_per_sqm: Union[int, float],
    hours: Union[int, float]
) -> float:
    """
    Converts solar irradiance from Watts per square meter (W/m²) to
    kilowatt-hours per square meter (kWh/m²) over a given period.

    This function is useful for estimating the total energy received on a surface
    when the average power (irradiance) over a specific duration is known.

    Args:
        irradiance_w_per_sqm: The average solar irradiance in W/m².
        hours: The number of hours over which the irradiance is applied.

    Returns:
        The total energy in kWh/m².

    Raises:
        ValueError: If irradiance or hours are negative.

    Example:
        >>> w_per_sqm_to_kwh_per_sqm(800, 5.5)
        4.4
    """
    if irradiance_w_per_sqm < 0:
        raise ValueError("Irradiance cannot be negative.")
    if hours < 0:
        raise ValueError("Hours cannot be negative.")

    # Energy (Wh) = Power (W) * time (h)
    energy_wh_per_sqm = irradiance_w_per_sqm * hours
    
    # Convert Wh to kWh by dividing by 1000
    energy_kwh_per_sqm = energy_wh_per_sqm / 1000.0
    
    return energy_kwh_per_sqm
