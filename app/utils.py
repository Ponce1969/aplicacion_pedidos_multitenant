"""Utilidades generales del proyecto."""

import re


def generar_slug(nombre: str) -> str:
    """Genera un slug URL-friendly a partir de un nombre.

    Ejemplos:
        "Barraca Pepe" -> "barraca-pepe"
        "Mi-Empresa 123" -> "mi-empresa-123"
        "José García" -> "jose-garcia"
        "  Espacios   " -> "espacios"
    """
    # Minúsculas
    slug = nombre.lower()

    # Reemplazar caracteres acentuados por equivalentes sin acento
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ü": "u", "ñ": "n", "ý": "y",
        "à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u",
        "ä": "a", "ë": "e", "ï": "i", "ö": "o", "ú": "u",
    }
    for accented, plain in replacements.items():
        slug = slug.replace(accented, plain)

    # Eliminar todo lo que no sea letra, número o espacio
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)

    # Reemplazar espacios y guiones múltiples por un solo guión
    slug = re.sub(r"[\s-]+", "-", slug)

    # Eliminar guiones al inicio o final
    slug = slug.strip("-")

    return slug


# ==================== RUT URUGUAYO ====================

# Pesos para el cálculo del dígito verificador del RUT uruguayo
# Se aplican de IZQUIERDA a DERECHA sobre los dígitos base
_RUT_WEIGHTS = [4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def normalizar_rut(rut: str) -> str:
    """Normaliza un RUT uruguayo a 12 dígitos puros.

    Elimina puntos, guiones y espacios. Rellena con ceros a la izquierda
    hasta completar 12 dígitos.

    Ejemplos:
        "21.479.785-0018"  -> "214797850018"  (RUT empresa)
        "21.479.785-0"      -> "0021479785000"   (sin DV explícito, se calcula)
        "1234567-8"         -> "000012345678"   (CI corta)

    Returns:
        RUT normalizado a 12 dígitos (sin puntos ni guiones).
        Si el input está vacío o es None, retorna string vacío.
    """
    if not rut or not rut.strip():
        return ""

    # Eliminar puntos, guiones, espacios
    digitos = re.sub(r"[^0-9]", "", rut)

    if not digitos:
        return ""

    # Separar número base del dígito verificador
    if len(digitos) > 1:
        base = digitos[:-1]
        dv_ingresado = digitos[-1].upper()
    else:
        base = digitos
        dv_ingresado = None

    # Calcular dígito verificador
    dv_calculado = _calcular_dv_rut(base)

    # Construir RUT normalizado: base rellenada a 11 dígitos + DV
    base_rellenada = base.zfill(11)
    return base_rellenada + dv_calculado


def validar_rut(rut: str) -> bool:
    """Valida que un RUT uruguayo sea correcto.

    Verifica el dígito verificador usando el algoritmo oficial de la DGI.

    Algoritmo:
    1. Tomar los dígitos base (sin DV)
    2. Multiplicar de izquierda a derecha por los pesos [4,3,2,9,8,7,6,5,4,3,2]
    3. Sumar productos
    4. DV = (11 - (suma mod 11)) mod 11
    5. Si DV = 10, se convierte en 0

    Args:
        rut: RUT en cualquier formato (con puntos, guiones, etc.)

    Returns:
        True si el RUT es válido, False en caso contrario.
    """
    if not rut or not rut.strip():
        return False

    digitos = re.sub(r"[^0-9]", "", rut)
    if len(digitos) < 2:
        return False

    base = digitos[:-1]
    dv_ingresado = digitos[-1].upper()

    dv_calculado = _calcular_dv_rut(base)

    return dv_ingresado == dv_calculado


def _calcular_dv_rut(base: str) -> str:
    """Calcula el dígito verificador de un RUT uruguayo.

    Algoritmo DGI (dirección de izquierda a derecha):
    1. Rellenar base con ceros a la izquierda hasta 11 dígitos
    2. Multiplicar cada dígito por el peso correspondiente: [4,3,2,9,8,7,6,5,4,3,2]
    3. Sumar productos
    4. DV = (11 - (suma mod 11)) mod 11
    5. Si DV = 10, se convierte en 0
    """
    base_rellenada = base.zfill(11)

    suma = 0
    for i, weight in enumerate(_RUT_WEIGHTS):
        suma += int(base_rellenada[i]) * weight

    dv = (11 - (suma % 11)) % 11

    # En Uruguay: 10 → 0
    if dv == 10:
        return "0"
    return str(dv)