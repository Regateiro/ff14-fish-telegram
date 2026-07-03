"""Tests for __main__.py (application entry point)."""

import pytest


@pytest.fixture(autouse=True)
def _mock_token(mocker):
    mocker.patch("ff14_fish_telegram.config.TELEGRAM_TOKEN", "test:token")


@pytest.fixture
def mock_app(mocker):
    app = mocker.MagicMock()
    app.bot_data = {}
    return app


@pytest.fixture
def mock_builder(mocker, mock_app):
    builder = mocker.MagicMock()
    builder.token.return_value = builder
    builder.post_init.return_value = builder
    builder.post_stop.return_value = builder
    builder.build.return_value = mock_app
    return builder


@pytest.mark.asyncio
async def test_refresh_fish_data_success(mocker, mock_app, sample_fish_data):
    mocker.patch(
        "ff14_fish_telegram.__main__.load_fish_data",
        mocker.AsyncMock(return_value=sample_fish_data),
    )
    from ff14_fish_telegram.__main__ import refresh_fish_data

    await refresh_fish_data(mock_app)
    assert mock_app.bot_data["fish_data"] is sample_fish_data


@pytest.mark.asyncio
async def test_refresh_fish_data_failure_does_not_raise(mocker, mock_app):
    mocker.patch(
        "ff14_fish_telegram.__main__.load_fish_data",
        mocker.AsyncMock(side_effect=Exception("Fetch failed")),
    )
    from ff14_fish_telegram.__main__ import refresh_fish_data

    await refresh_fish_data(mock_app)
    assert "fish_data" not in mock_app.bot_data


@pytest.mark.asyncio
async def test_reminder_job_success(mocker, mock_app):
    mocker.patch(
        "ff14_fish_telegram.__main__.check_reminders",
        mocker.AsyncMock(),
    )
    from ff14_fish_telegram.__main__ import reminder_job

    await reminder_job(mock_app)


@pytest.mark.asyncio
async def test_reminder_job_failure_does_not_raise(mocker, mock_app):
    mocker.patch(
        "ff14_fish_telegram.__main__.check_reminders",
        mocker.AsyncMock(side_effect=Exception("Reminder error")),
    )
    from ff14_fish_telegram.__main__ import reminder_job

    await reminder_job(mock_app)


@pytest.mark.asyncio
async def test_post_init(mocker, mock_app, sample_fish_data):
    mock_init_db = mocker.patch("ff14_fish_telegram.__main__.init_db")
    mocker.patch(
        "ff14_fish_telegram.__main__.load_fish_data",
        mocker.AsyncMock(return_value=sample_fish_data),
    )
    mock_scheduler = mocker.patch(
        "ff14_fish_telegram.__main__.AsyncIOScheduler", autospec=True,
    )
    from ff14_fish_telegram.__main__ import post_init

    await post_init(mock_app)

    mock_init_db.assert_called_once()
    assert mock_app.bot_data["fish_data"] is sample_fish_data
    scheduler_instance = mock_scheduler.return_value
    scheduler_instance.add_job.assert_called()
    scheduler_instance.start.assert_called_once()
    assert mock_app.bot_data["scheduler"] is scheduler_instance


@pytest.mark.asyncio
async def test_post_stop_shuts_down_scheduler(mocker, mock_app):
    fake_scheduler = mocker.MagicMock()
    mock_app.bot_data["scheduler"] = fake_scheduler
    from ff14_fish_telegram.__main__ import post_stop

    await post_stop(mock_app)
    fake_scheduler.shutdown.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_post_stop_no_scheduler_does_not_raise(mocker, mock_app):
    from ff14_fish_telegram.__main__ import post_stop

    await post_stop(mock_app)


def test_main(mocker, mock_app, mock_builder):
    mocker.patch(
        "ff14_fish_telegram.__main__.ApplicationBuilder",
        return_value=mock_builder,
    )
    from telegram.ext import BaseHandler

    dummy_handler = mocker.MagicMock(spec=BaseHandler)
    mock_get_handlers = mocker.patch(
        "ff14_fish_telegram.__main__.get_handlers",
        return_value=[dummy_handler],
    )
    from ff14_fish_telegram.__main__ import main

    main()

    mock_builder.token.assert_called_once()
    mock_builder.post_init.assert_called_once()
    mock_builder.post_stop.assert_called_once()
    mock_builder.build.assert_called_once()
    mock_get_handlers.assert_called_once()
    mock_app.add_handler.assert_called_once_with(dummy_handler)
    mock_app.run_polling.assert_called_once_with(
        allowed_updates=["message", "callback_query"],
    )
