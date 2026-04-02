from __future__ import annotations


def run_collection_cycle(app) -> None:
    with app.state.db.session_scope() as session:
        app.state.collection_service.collect_all(session)
