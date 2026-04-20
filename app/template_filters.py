"""Filtros Jinja2 personalizados para formateo de moneda.

Usa Decimal internamente para evitar errores de punto flotante.
Ejemplo: {{ precio|pesos }} → "$ 1.250"
"""

from decimal import Decimal, InvalidOperation


def format_pesos(value: Decimal | float | str | int | None) -> str:
    """Formatea un valor numérico como pesos uruguayos.

    Usa Decimal internamente para cálculos precisos.
    Separador de miles: punto (convención uruguaya).
    Sin decimales para montos enteros, con 2 decimales si aplica.

    Args:
        value: Valor a formatear. Acepta Decimal, float, str, int o None.

    Returns:
        String formateado como "$ 1.250" o "$ 0" si es None/vacío.

    Examples:
        >>> format_pesos(Decimal("1250"))
        '$ 1.250'
        >>> format_pesos(1250)
        '$ 1.250'
        >>> format_pesos(Decimal("1250.50"))
        '$ 1.250,50'
        >>> format_pesos(None)
        '$ 0'
    """
    if value is None:
        return "$ 0"

    try:
        # Convertir a Decimal para precisión
        if isinstance(value, Decimal):
            d = value
        elif isinstance(value, float):
            # float → str → Decimal para evitar errores de representación
            d = Decimal(str(value))
        else:
            d = Decimal(str(value))

        # Quantizar a 2 decimales
        d = d.quantize(Decimal("0.01"))

        # Separar parte entera y decimal
        int_part = int(d)
        dec_part = d - Decimal(int_part)

        # Formatear parte entera con puntos como separador de miles
        int_formatted = f"{int_part:,}".replace(",", ".")

        # Si tiene decimales significativos, agregarlos con coma
        if dec_part == 0:
            return f"$ {int_formatted}"
        else:
            dec_str = f"{dec_part:.2f}"[2:]  # "50" de 0.50
            return f"$ {int_formatted},{dec_str}"

    except (InvalidOperation, ValueError, TypeError):
        return f"$ {value}"


def format_cantidad(value: Decimal | float | str | int | None) -> str:
    """Formatea una cantidad (sin símbolo de moneda).

    Para cantidades que no son dinero (kg, litros, unidades).
    Usa Decimal para precisión.

    Args:
        value: Valor a formatear.

    Returns:
        String formateado. "1" si es entero, "1,50" si tiene decimales.

    Examples:
        >>> format_cantidad(Decimal("1.00"))
        '1'
        >>> format_cantidad(Decimal("1.50"))
        '1,50'
    """
    if value is None:
        return "0"

    try:
        if isinstance(value, Decimal):
            d = value
        elif isinstance(value, float):
            d = Decimal(str(value))
        else:
            d = Decimal(str(value))

        d = d.quantize(Decimal("0.01"))

        # Si es entero, mostrar sin decimales
        if d == d.to_integral_value():
            return str(int(d))

        # Si tiene decimales, usar coma
        return str(d).replace(".", ",")

    except (InvalidOperation, ValueError, TypeError):
        return str(value)
