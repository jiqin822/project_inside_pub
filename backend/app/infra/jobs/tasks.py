"""Background job tasks."""
from app.infra.messaging.redis_bus import redis_bus
from app.infra.db.session import get_db
from app.infra.db.repositories.session_repo import SessionReportRepositoryImpl, NudgeEventRepositoryImpl
from app.domain.coach.analyzers.review_engine import ReviewEngine


async def process_generate_session_report_job(session_id: str):
    """Process generate session report job."""
    async for db in get_db():
        # Get nudge events
        nudge_repo = NudgeEventRepositoryImpl(db)
        events = await nudge_repo.list_by_session(session_id)
        event_dicts = [e for e in events]

        # Generate report
        review_engine = ReviewEngine()
        report = review_engine.generate_report(session_id, event_dicts)

        # Save or update report
        report_repo = SessionReportRepositoryImpl(db)
        existing = await report_repo.get_by_session_id(session_id)
        if existing:
            # Update existing report
            from app.infra.db.models.session import SessionReportModel, ReportStatus
            from sqlalchemy import update
            await db.execute(
                update(SessionReportModel)
                .where(SessionReportModel.session_id == session_id)
                .values(
                    summary=report.summary,
                    moments=report.moments,
                    action_items=report.action_items,
                    status=ReportStatus.READY,
                )
            )
            await db.commit()
        else:
            await report_repo.create(report)
        break  # Only use first session


async def worker_loop():
    """Worker loop to process jobs."""
    await redis_bus.connect()
    while True:
        job = await redis_bus.get_job("jobs")
        if job:
            job_type = job.get("type")
            job_data = job.get("data", {})
            if job_type == "generate_session_report":
                session_id = job_data.get("session_id")
                if session_id:
                    await process_generate_session_report_job(session_id)
            elif job_type == "finalize_session":  # Legacy support
                session_id = job_data.get("session_id")
                if session_id:
                    await process_generate_session_report_job(session_id)
