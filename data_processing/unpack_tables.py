from functools import reduce

def unpack_source_grade_table(
    source_table: dict[str, dict[str, float]],
    *,
    allowed_grades_fn
) -> dict:
    """
    Converts {item: {source: max_grade}} into:
    {item: {source: [allowed_grades], core: [intersection]}}
    """
    result = {}

    for item, sources in source_table.items():
        result[item] = {}

        for source, max_grade in sources.items():
            if max_grade is None:
                continue
            result[item][source] = sorted(allowed_grades_fn(max_grade))

        source_sets = [
            set(grades) for grades in result[item].values()
            if grades
        ]

        result[item]["core"] = (
            sorted(reduce(set.intersection, source_sets))
            if source_sets else []
        )

    return result
