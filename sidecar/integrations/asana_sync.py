"""Sync logic for pulling/pushing entities between Asana and the sidecar DB.

Pull sync: Asana → sidecar (upsert by asana_gid)
Push sync: sidecar → Asana (create/update Asana objects from sidecar records)
"""

# TODO (Task #13): Implement pull and push sync per entity type.
