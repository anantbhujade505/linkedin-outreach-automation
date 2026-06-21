from models.schemas import ExtractedProfile, ProfileStatus, RunStatus
from repositories.sqlite_repository import SQLiteRepository


def test_repository_tracks_run_profile_message_and_followup(test_settings) -> None:
    repo = SQLiteRepository(test_settings.sqlite_path)
    repo.create_run("run-1", "outreach")
    profile_id = repo.upsert_profile("https://www.linkedin.com/in/example/", "Alex", "Example", 2)
    repo.update_profile_context(
        profile_id,
        ExtractedProfile(
            profile_url="https://www.linkedin.com/in/example/",
            name="Alex Example",
            headline="AI Engineer",
            current_role="Principal Engineer",
        ),
    )
    repo.record_message("run-1", profile_id, "connection_note", "draft", "reviewed", "final", 200)
    repo.record_action("run-1", "connection_request", "success", profile_id)
    repo.create_or_update_followup(profile_id, "2026-01-01T00:00:00+00:00")
    assert len(repo.pending_followups("2026-02-01T00:00:00+00:00")) == 1
    repo.update_profile_status(profile_id, ProfileStatus.REQUEST_SENT)
    repo.finish_run("run-1", RunStatus.SUCCESS)
    assert repo.count_actions_since("connection_request", "2025-01-01T00:00:00+00:00") == 1
