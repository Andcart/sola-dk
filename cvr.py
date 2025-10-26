import re

def is_valid_cvr(cvr: str) -> bool:
    """
    Validates a Danish CVR number (Det Centrale Virksomhedsregister).

    A CVR number is an 8-digit number used to identify businesses in Denmark.
    This function validates the CVR number based on its format and a
    modulus-11 check.

    Args:
        cvr (str): The CVR number to validate, which can include spaces or hyphens.

    Returns:
        bool: True if the CVR number is valid, False otherwise.
    """
    # Ensure input is a string
    if not isinstance(cvr, str):
        return False

    # Clean the input string by removing common separators
    cleaned_cvr = cvr.replace(" ", "").replace("-", "")

    # Check if the cleaned string consists of 8 digits
    if not re.fullmatch(r"\d{8}", cleaned_cvr):
        return False

    # Perform the modulus-11 check
    weights = [2, 7, 6, 5, 4, 3, 2, 1]
    try:
        mod11_sum = sum(int(digit) * weight for digit, weight in zip(cleaned_cvr, weights))
    except ValueError:
        # This case should not be reached due to the regex check, but is included for robustness.
        return False

    return mod11_sum % 11 == 0
