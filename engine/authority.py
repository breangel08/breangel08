"""Conservative interpretation boundary for free-form nonnegotiable requirements."""
import re

SUPPORTED = {
    "exact assets": [r"\bexact\b.*\b(asset|image|logo|copy|imagery)", r"preserve.*(asset|image|logo|copy|imagery)", r"original.*(asset|image|logo)"],
    "authorized content": [r"(supplied|approved|authorized).*copy", r"no.*(invented|fake|unauthorized).*(claim|review|testimonial|stat|copy|fact)", r"use only.*(supplied|approved)"],
    "no decoration": [r"no.*(gradient|pill|icon strip|decorative|card grid|testimonial|statistic)", r"avoid.*(gradient|pill|card grid)"],
    "accessibility": [r"\b(accessib|wcag|keyboard|reduced.motion|semantic|contrast)"],
    "responsive": [r"\b(responsive|mobile|tablet)"],
    "brand tokens": [r"^#[0-9a-f]{6}", r"^(Georgia|Arial|Helvetica|Times New Roman)(\s*,|$)", r"^preserve exact asset a_"],
}


def interpret(project):
    records=[]
    for rule in project['brief']['requirements']:
        text=rule['text'];classification=rule['classification']
        if classification in {'PREFERRED','ALLOWED','AVOID'}:
            records.append({'rule':rule,'status':'ADVISORY','basis':'Preserved in strategy and review authority'});continue
        matched=[name for name,patterns in SUPPORTED.items() if any(re.search(pattern,text,re.I) for pattern in patterns)]
        # Recognized semantics are deliberately narrow. Never label arbitrary prose
        # implemented solely because a human will later see the visual prototype.
        records.append({'rule':rule,'status':'SUPPORTED' if matched else 'NEEDS_STRUCTURED_AUTHORITY','enforced_by':matched,'basis':'Explicit renderer/hash/content/QA contract' if matched else 'No safely inferable implemented contract for this absolute'})
    return records
