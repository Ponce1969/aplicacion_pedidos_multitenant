"""Utilidades generales del proyecto."""


def generar_slug(nombre: str) -> str:
    """Genera un slug URL-friendly a partir de un nombre.

    Ejemplos:
        "Barraca Pepe" -> "barraca-pepe"
        "Mi-Empresa 123" -> "mi-empresa-123"
        "José García" -> "jose-garcia"
        "  Espacios   " -> "espacios"
    """
    import re

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