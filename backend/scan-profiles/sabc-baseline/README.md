# sabc-baseline InSpec profile (GENERATED — do not hand-edit)

Generated from the unified SABC referential at seed time. One control per
referential control, each guarded by `os.family` so only the family-correct
check runs on a given node. The check runs the family's **Validate** procedure
and asserts exit status 0. Both Debian and Red Hat families ship ready.
