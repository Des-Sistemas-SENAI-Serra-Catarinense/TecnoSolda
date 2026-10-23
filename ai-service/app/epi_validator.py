from .models import Evidence, Frame


def visible_equipment(frame: Frame) -> dict[str, Evidence]:
    return {
        "avental": frame.apron,
        "luva_esquerda": frame.left_glove,
        "luva_direita": frame.right_glove,
    }


def all_present(equipment: dict[str, Evidence]) -> bool:
    return all(value == Evidence.PRESENT for value in equipment.values())
