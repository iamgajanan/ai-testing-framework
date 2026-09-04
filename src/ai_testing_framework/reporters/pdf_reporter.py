"""PDF reporting is intentionally deferred to Phase 2.

The Phase 1 contract is HTML + JSON reporting. This module provides a clear
extension point without adding a heavyweight PDF dependency to the MVP.
"""


def write_pdf_report(*args, **kwargs):
    raise NotImplementedError("PDF reporting is planned for a later phase; use HTML or JSON in Phase 1.")
