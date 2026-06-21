from utils.validators import enforce_limit, is_linkedin_profile_url, validate_message


def test_linkedin_profile_url_validation() -> None:
    assert is_linkedin_profile_url("https://www.linkedin.com/in/example/")
    assert not is_linkedin_profile_url("https://www.linkedin.com/company/example/")
    assert not is_linkedin_profile_url("https://example.com/in/person/")


def test_message_validation_blocks_sales_language() -> None:
    errors = validate_message(
        "Hi Alex, book a demo with our product and get a guaranteed 10x result.",
        200,
        ["Alex", "AI Engineering"],
    )
    assert errors


def test_enforce_limit_trims_cleanly() -> None:
    assert len(enforce_limit("hello " * 20, 30)) <= 30
