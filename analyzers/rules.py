def get_articulation_confidence(note, rules, grade):
    # Map music21 articulation names to our field names
    art_mapping = {
        'staccato': 'staccato',
        'tenuto': 'tenuto',
        'accent': 'accent',
        'strongAccent': 'marcato',  # marcato is strongAccent in music21
        'slur': 'slur'
    }
    
    articulations = [art_mapping.get(art.name, art.name) for art in note.articulations]
    
    if len(articulations) > 1:
        return (1, None, None) if rules[grade].multiple_articulations else (0, f"Multiple articulations per note are not common for grade {grade}", "multiple_articulations")
    else:
        for art in articulations:
            if hasattr(rules[grade], art):
                return (1, None, None) if getattr(rules[grade], art) else (0, f"{art} is not common for grade {grade}", art)
        return (1, None, None)  # If no recognized articulation, assume ok